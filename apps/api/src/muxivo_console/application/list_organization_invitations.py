"""List organization membership invitations for authorized administrators."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    OrganizationInvitationReader,
    OrganizationMembershipReader,
)
from muxivo_console.domain.organization_invitations import OrganizationInvitation
from muxivo_console.domain.organizations import OrganizationRole

logger = logging.getLogger(__name__)


class OrganizationInvitationListingRejectedError(PermissionError):
    """Raised when an actor cannot inspect organization invitations."""


@dataclass(frozen=True, slots=True)
class ListOrganizationInvitationsCommand:
    actor_id: UUID
    organization_id: UUID
    correlation_id: UUID


@dataclass(slots=True)
class ListOrganizationInvitations:
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
            await self.invitations.list_for_organization(
                organization_id=command.organization_id
            )
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
