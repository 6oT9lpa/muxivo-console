"""List organizations available to the current Console user."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.list_organizations_command import ListOrganizationsCommand
from muxivo_console.application.organization_list_rejected_error import (
    OrganizationListRejectedError,
)
from muxivo_console.application.ports import OrganizationListingReader, UserStatusReader
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import OrganizationMembershipProfile

logger = logging.getLogger("muxivo_console.application.list_organizations")


@dataclass(slots=True)
class ListOrganizations:
    """Read the organizations where the actor has an active membership."""

    user_statuses: UserStatusReader
    organizations: OrganizationListingReader

    async def execute(
        self, command: ListOrganizationsCommand
    ) -> tuple[OrganizationMembershipProfile, ...]:
        logger.info(
            "organization.list.started",
            extra={
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "organization.list.rejected_inactive_user",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationListRejectedError("The user is not allowed to list organizations.")
        organizations = tuple(await self.organizations.list_for_actor(actor_id=command.actor_id))
        logger.info(
            "organization.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
                "organization_count": len(organizations),
            },
        )
        return organizations
