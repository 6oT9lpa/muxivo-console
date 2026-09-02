"""Use cases for Console-owned organization membership management."""

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailLookupHasher,
    IdentifierGenerator,
    OrganizationMemberReader,
    OrganizationMembershipReader,
    OrganizationMemberWriter,
    UserEmailLookupReader,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    OrganizationMemberProfile,
    OrganizationMembership,
    OrganizationRole,
)

logger = logging.getLogger(__name__)


class OrganizationMemberManagementRejectedError(PermissionError):
    """Raised when a membership operation must fail closed."""


@dataclass(frozen=True, slots=True)
class ListOrganizationMembersCommand:
    actor_id: UUID
    organization_id: UUID
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class AddOrganizationMemberCommand:
    actor_id: UUID
    organization_id: UUID
    email: str
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class UpdateOrganizationMemberCommand:
    actor_id: UUID
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class RemoveOrganizationMemberCommand:
    actor_id: UUID
    organization_id: UUID
    user_id: UUID
    correlation_id: UUID


@dataclass(slots=True)
class ListOrganizationMembers:
    memberships: OrganizationMembershipReader
    members: OrganizationMemberReader

    async def execute(
        self, command: ListOrganizationMembersCommand
    ) -> tuple[OrganizationMemberProfile, ...]:
        logger.info(
            "organization.members.list.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=command.organization_id
        )
        if actor is None or actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
            logger.warning(
                "organization.members.list.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Access denied.")
        members = tuple(await self.members.list_profiles(command.organization_id))
        logger.info(
            "organization.members.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "member_count": len(members),
                "correlation_id": str(command.correlation_id),
            },
        )
        return members


@dataclass(slots=True)
class AddOrganizationMember:
    identifiers: IdentifierGenerator
    email_normalizer: EmailAddressNormalizer
    email_lookup_hasher: EmailLookupHasher
    invitees: UserEmailLookupReader
    user_statuses: UserStatusReader
    memberships: OrganizationMembershipReader
    members: OrganizationMemberWriter

    async def execute(self, command: AddOrganizationMemberCommand) -> OrganizationMembership:
        normalized_email = self.email_normalizer.normalize(command.email)
        email_lookup_hash = self.email_lookup_hasher.lookup_hash(normalized_email)
        logger.info(
            "organization.member.add.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_email_lookup_hash_prefix": email_lookup_hash[:12],
                "role": command.role.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await _require_actor_can_manage(
            self.memberships, command.actor_id, command.organization_id, command.role
        )
        _reject_scopes_not_supported_by_role(
            role=command.role,
            scopes=command.resource_scopes,
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            correlation_id=command.correlation_id,
            operation="add",
        )
        target_user_id = await self.invitees.find_active_user_id_by_email_lookup_hash(
            email_lookup_hash=email_lookup_hash
        )
        if target_user_id is None:
            logger.warning(
                "organization.member.add.rejected_unknown_invitee",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_email_lookup_hash_prefix": email_lookup_hash[:12],
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Invitee user is unavailable.")
        if await self.user_statuses.get_status(user_id=target_user_id) is not UserStatus.ACTIVE:
            logger.warning(
                "organization.member.add.rejected_inactive_target",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(target_user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Target user is not active.")
        membership = OrganizationMembership(
            id=self.identifiers.new(),
            actor_id=target_user_id,
            organization_id=command.organization_id,
            role=command.role,
            resource_scopes=_assign_scope_ids(self.identifiers, command.resource_scopes),
        )
        created = await self.members.add_member(
            membership=membership,
            audit_event=_audit_event(
                self.identifiers,
                command.correlation_id,
                command.actor_id,
                command.organization_id,
                "organization.member.add",
                target_user_id,
            ),
        )
        if not created:
            logger.warning(
                "organization.member.add.conflict",
                extra={
                    "actor_id": str(actor.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(target_user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Member could not be added.")
        logger.info(
            "organization.member.add.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "membership_id": str(membership.id),
                "target_user_id": str(target_user_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return membership


@dataclass(slots=True)
class UpdateOrganizationMember:
    identifiers: IdentifierGenerator
    memberships: OrganizationMembershipReader
    members: OrganizationMemberWriter

    async def execute(self, command: UpdateOrganizationMemberCommand) -> OrganizationMembership:
        logger.info(
            "organization.member.update.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_user_id": str(command.user_id),
                "role": command.role.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await _require_actor_can_manage(
            self.memberships, command.actor_id, command.organization_id, command.role
        )
        _reject_scopes_not_supported_by_role(
            role=command.role,
            scopes=command.resource_scopes,
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            correlation_id=command.correlation_id,
            operation="update",
        )
        target = await self.memberships.get_membership(
            actor_id=command.user_id, organization_id=command.organization_id
        )
        if (
            target is None
            or target.id is None
            or target.actor_id == actor.actor_id
            or not actor.role.may_assign(target.role)
        ):
            logger.warning(
                "organization.member.update.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(command.user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Member update denied.")
        updated = OrganizationMembership(
            id=target.id,
            actor_id=target.actor_id,
            organization_id=target.organization_id,
            role=command.role,
            resource_scopes=_assign_scope_ids(self.identifiers, command.resource_scopes),
        )
        saved = await self.members.update_member(
            membership=updated,
            audit_event=_audit_event(
                self.identifiers,
                command.correlation_id,
                command.actor_id,
                command.organization_id,
                "organization.member.update",
                command.user_id,
            ),
        )
        if not saved:
            raise OrganizationMemberManagementRejectedError("Member update failed.")
        logger.info(
            "organization.member.update.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_user_id": str(command.user_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return updated


@dataclass(slots=True)
class RemoveOrganizationMember:
    identifiers: IdentifierGenerator
    memberships: OrganizationMembershipReader
    members: OrganizationMemberWriter

    async def execute(self, command: RemoveOrganizationMemberCommand) -> None:
        logger.info(
            "organization.member.remove.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_user_id": str(command.user_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=command.organization_id
        )
        target = await self.memberships.get_membership(
            actor_id=command.user_id, organization_id=command.organization_id
        )
        if (
            actor is None
            or target is None
            or target.id is None
            or target.actor_id == actor.actor_id
            or not actor.role.may_assign(target.role)
        ):
            logger.warning(
                "organization.member.remove.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(command.user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Member removal denied.")
        removed = await self.members.remove_member(
            membership_id=target.id,
            audit_event=_audit_event(
                self.identifiers,
                command.correlation_id,
                command.actor_id,
                command.organization_id,
                "organization.member.remove",
                command.user_id,
            ),
        )
        if not removed:
            raise OrganizationMemberManagementRejectedError("Member removal failed.")
        logger.info(
            "organization.member.remove.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_user_id": str(command.user_id),
                "correlation_id": str(command.correlation_id),
            },
        )


async def _require_actor_can_manage(
    memberships: OrganizationMembershipReader,
    actor_id: UUID,
    organization_id: UUID,
    target_role: OrganizationRole,
) -> OrganizationMembership:
    actor = await memberships.get_membership(actor_id=actor_id, organization_id=organization_id)
    if actor is None or not actor.role.may_assign(target_role):
        logger.warning(
            "organization.member.manage.denied",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "target_role": target_role.value,
            },
        )
        raise OrganizationMemberManagementRejectedError("Member management denied.")
    return actor


def _assign_scope_ids(
    identifiers: IdentifierGenerator, scopes: tuple[MembershipResourceScope, ...]
) -> frozenset[MembershipResourceScope]:
    return frozenset(
        MembershipResourceScope(
            id=scope.id or identifiers.new(),
            resource=scope.resource,
            action=scope.action,
        )
        for scope in scopes
    )


def _reject_scopes_not_supported_by_role(
    *,
    role: OrganizationRole,
    scopes: tuple[MembershipResourceScope, ...],
    actor_id: UUID,
    organization_id: UUID,
    correlation_id: UUID,
    operation: str,
) -> None:
    unsupported = [scope for scope in scopes if not role.supports_scope(scope)]
    if not unsupported:
        return
    logger.warning(
        "organization.member.scopes.rejected",
        extra={
            "actor_id": str(actor_id),
            "organization_id": str(organization_id),
            "role": role.value,
            "operation": operation,
            "unsupported_scope_count": len(unsupported),
            "correlation_id": str(correlation_id),
        },
    )
    raise OrganizationMemberManagementRejectedError("Role does not support requested scopes.")


def _audit_event(
    identifiers: IdentifierGenerator,
    correlation_id: UUID,
    actor_id: UUID,
    organization_id: UUID,
    action: str,
    target_user_id: UUID,
) -> AuditEvent:
    return AuditEvent(
        id=identifiers.new(),
        correlation_id=correlation_id,
        actor_id=actor_id,
        organization_id=organization_id,
        action=action,
        resource_type="organization_member",
        resource_id=str(target_user_id),
        result="succeeded",
    )
