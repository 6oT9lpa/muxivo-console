"""Change a Console organization role without crossing platform trust boundaries."""

from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationAuthorizer,
    OrganizationMembershipReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.organizations import OrganizationMember, OrganizationRole


class OrganizationMemberNotFoundError(LookupError):
    """The selected membership does not belong to the selected Console tenant."""


class OrganizationRoleChangeRejectedError(ValueError):
    """The requested role transition violates Console hierarchy rules."""


class OrganizationRoleChangeConflictError(RuntimeError):
    """Membership state changed after authorization and must be reloaded."""


class OrganizationMemberLookup(Protocol):
    async def find_for_organization(
        self, *, organization_id: UUID, membership_id: UUID
    ) -> OrganizationMember | None: ...


class OrganizationMemberRoleWriter(Protocol):
    """Atomically compare membership state, change the role and append audit."""

    async def change_role(
        self,
        *,
        organization_id: UUID,
        actor_membership_id: UUID,
        actor_id: UUID,
        expected_actor_role: OrganizationRole,
        membership_id: UUID,
        target_user_id: UUID,
        expected_role: OrganizationRole,
        new_role: OrganizationRole,
        audit_event: AuditEvent,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class ChangeOrganizationMemberRoleCommand:
    actor_id: UUID
    organization_id: UUID
    membership_id: UUID
    role: OrganizationRole
    correlation_id: UUID


@dataclass(slots=True)
class ChangeOrganizationMemberRole:
    authorizer: OrganizationAuthorizer
    memberships: OrganizationMembershipReader
    members: OrganizationMemberLookup
    roles: OrganizationMemberRoleWriter
    identifiers: IdentifierGenerator

    async def execute(
        self, command: ChangeOrganizationMemberRoleCommand
    ) -> OrganizationMember:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                resource=AuthorizationResource.ORGANIZATION_MEMBERSHIPS,
                action=AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to manage organization members.")

        actor_membership = await self.memberships.get_membership(
            actor_id=command.actor_id,
            organization_id=command.organization_id,
        )
        if actor_membership is None or actor_membership.id is None:
            raise AccessDeniedError("The actor membership is unavailable.")

        target = await self.members.find_for_organization(
            organization_id=command.organization_id,
            membership_id=command.membership_id,
        )
        if target is None:
            raise OrganizationMemberNotFoundError("Organization member was not found.")
        if target.role is command.role:
            return target

        self._validate_transition(
            actor_role=actor_membership.role,
            current_role=target.role,
            new_role=command.role,
        )
        audit_event = AuditEvent(
            id=self.identifiers.new(),
            correlation_id=command.correlation_id,
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            action="organization.membership_role_changed",
            resource_type="organization_membership",
            resource_id=str(target.membership_id),
            result="succeeded",
        )
        changed = await self.roles.change_role(
            organization_id=command.organization_id,
            actor_membership_id=actor_membership.id,
            actor_id=command.actor_id,
            expected_actor_role=actor_membership.role,
            membership_id=target.membership_id,
            target_user_id=target.user_id,
            expected_role=target.role,
            new_role=command.role,
            audit_event=audit_event,
        )
        if not changed:
            raise OrganizationRoleChangeConflictError(
                "Organization membership state changed; reload before retrying."
            )
        return replace(target, role=command.role)

    @staticmethod
    def _validate_transition(
        *,
        actor_role: OrganizationRole,
        current_role: OrganizationRole,
        new_role: OrganizationRole,
    ) -> None:
        if current_role is OrganizationRole.OWNER or new_role is OrganizationRole.OWNER:
            raise OrganizationRoleChangeRejectedError(
                "Owner changes require the dedicated ownership-transfer flow."
            )
        if not actor_role.may_assign(current_role):
            raise OrganizationRoleChangeRejectedError(
                "An actor cannot modify an equal or more privileged role."
            )
        if not actor_role.may_assign(new_role):
            raise OrganizationRoleChangeRejectedError(
                "An actor cannot grant an equal or more privileged role."
            )
