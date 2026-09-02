"""Use case for revoking a pending organization membership invitation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.organization_invitation_revocation_error import (
    OrganizationInvitationRevocationRejectedError,
)
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    OrganizationInvitationReader,
    OrganizationInvitationWriter,
    OrganizationMembershipReader,
)
from muxivo_console.application.revoke_organization_invitation_command import (
    RevokeOrganizationInvitationCommand,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organization_invitations import OrganizationInvitationStatus

logger = logging.getLogger("muxivo_console.application.revoke_organization_invitation")


@dataclass(slots=True)
class RevokeOrganizationInvitation:
    """Revoke a pending invitation when the actor can assign its role."""

    clock: Clock
    identifiers: IdentifierGenerator
    memberships: OrganizationMembershipReader
    invitations: OrganizationInvitationReader
    writer: OrganizationInvitationWriter

    async def execute(self, command: RevokeOrganizationInvitationCommand) -> None:
        logger.info(
            "organization.invitation.revoke.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "invitation_id": str(command.invitation_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=command.organization_id
        )
        invitation = await self.invitations.find_for_organization(
            organization_id=command.organization_id, invitation_id=command.invitation_id
        )
        if (
            actor is None
            or invitation is None
            or not actor.role.may_assign(invitation.role)
            or invitation.status_at(self.clock.now()) is not OrganizationInvitationStatus.PENDING
        ):
            logger.warning(
                "organization.invitation.revoke.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "invitation_id": str(command.invitation_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationRevocationRejectedError("Invitation revocation denied.")
        revoked = await self.writer.revoke(
            invitation_id=invitation.id,
            organization_id=invitation.organization_id,
            revoked_at=self.clock.now(),
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                action="organization.member.invitation.revoked",
                resource_type="organization_invitation",
                resource_id=str(invitation.id),
                result="succeeded",
            ),
        )
        if not revoked:
            logger.warning(
                "organization.invitation.revoke.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "invitation_id": str(command.invitation_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationRevocationRejectedError("Invitation revocation failed.")
        logger.info(
            "organization.invitation.revoke.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "invitation_id": str(command.invitation_id),
                "correlation_id": str(command.correlation_id),
            },
        )
