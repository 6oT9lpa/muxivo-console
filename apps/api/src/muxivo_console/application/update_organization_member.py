"""Use case for changing an organization's member role and scopes."""

import logging
from dataclasses import dataclass

from muxivo_console.application.organization_member_management_error import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.organization_member_management_helpers import (
    assign_scope_ids,
    create_member_audit_event,
    reject_scopes_not_supported_by_role,
    require_actor_can_manage,
)
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationMembershipReader,
    OrganizationMemberWriter,
)
from muxivo_console.application.update_organization_member_command import (
    UpdateOrganizationMemberCommand,
)
from muxivo_console.domain.organizations import OrganizationMembership

logger = logging.getLogger("muxivo_console.application.manage_organization_members")


@dataclass(slots=True)
class UpdateOrganizationMember:
    """Update only members below the actor's role in the organization hierarchy."""

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
        actor = await require_actor_can_manage(
            self.memberships, command.actor_id, command.organization_id, command.role
        )
        reject_scopes_not_supported_by_role(
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
            resource_scopes=assign_scope_ids(self.identifiers, command.resource_scopes),
        )
        saved = await self.members.update_member(
            membership=updated,
            audit_event=create_member_audit_event(
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
