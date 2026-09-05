"""Use case for removing an organization member."""

import logging
from dataclasses import dataclass

from muxivo_console.application.organization_member_management_error import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.organization_member_management_helpers import (
    can_manage_organization_members,
    create_member_audit_event,
)
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationMembershipReader,
    OrganizationMemberWriter,
)
from muxivo_console.application.remove_organization_member_command import (
    RemoveOrganizationMemberCommand,
)

logger = logging.getLogger("muxivo_console.application.manage_organization_members")


@dataclass(slots=True)
class RemoveOrganizationMember:
    """Remove a member only when the actor outranks the target member."""

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
            or not can_manage_organization_members(actor.role)
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
            audit_event=create_member_audit_event(
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
