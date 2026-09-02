"""Use case for listing organization membership invitations."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.list_organization_invitations_command import (
    ListOrganizationInvitationsCommand,
)
from muxivo_console.application.organization_invitation_listing_error import (
    OrganizationInvitationListingRejectedError,
)
from muxivo_console.application.ports import (
    OrganizationInvitationReader,
    OrganizationMembershipReader,
)
from muxivo_console.domain.organization_invitations import OrganizationInvitation
from muxivo_console.domain.organizations import OrganizationRole

logger = logging.getLogger("muxivo_console.application.list_organization_invitations")


@dataclass(slots=True)
class ListOrganizationInvitations:
    """Read invitations for owners and administrators without exposing tokens."""

    memberships: OrganizationMembershipReader
    invitations: OrganizationInvitationReader

    async def execute(
        self, command: ListOrganizationInvitationsCommand
    ) -> tuple[OrganizationInvitation, ...]:
        logger.info(
            "organization.invitation.list.started",
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
                "organization.invitation.list.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationListingRejectedError("Access denied.")
        result = tuple(
            await self.invitations.list_for_organization(organization_id=command.organization_id)
        )
        logger.info(
            "organization.invitation.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "invitation_count": len(result),
                "correlation_id": str(command.correlation_id),
            },
        )
        return result
