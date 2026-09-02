"""Use case for listing organization members."""

import logging
from dataclasses import dataclass

from muxivo_console.application.list_organization_members_command import (
    ListOrganizationMembersCommand,
)
from muxivo_console.application.organization_member_management_error import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.ports import OrganizationMemberReader, OrganizationMembershipReader
from muxivo_console.domain.organizations import OrganizationMemberProfile, OrganizationRole

logger = logging.getLogger("muxivo_console.application.manage_organization_members")


@dataclass(slots=True)
class ListOrganizationMembers:
    """Read organization members for owners and administrators."""

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
