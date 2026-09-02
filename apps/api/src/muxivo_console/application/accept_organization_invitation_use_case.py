"""Use case for accepting an organization invitation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.accept_organization_invitation_command import (
    AcceptOrganizationInvitationCommand,
)
from muxivo_console.application.organization_invitation_acceptance_error import (
    OrganizationInvitationAcceptanceRejectedError,
)
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    OrganizationInvitationReader,
    OrganizationInvitationWriter,
    OrganizationMembershipReader,
    SessionTokenHasher,
    UserEmailLookupReader,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organization_invitations import OrganizationInvitationStatus
from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationMembership

logger = logging.getLogger("muxivo_console.application.accept_organization_invitation")


@dataclass(slots=True)
class AcceptOrganizationInvitation:
    """Consume a valid invitation for the account owning its protected e-mail."""

    clock: Clock
    identifiers: IdentifierGenerator
    token_hasher: SessionTokenHasher
    user_emails: UserEmailLookupReader
    user_statuses: UserStatusReader
    memberships: OrganizationMembershipReader
    invitations: OrganizationInvitationReader
    writer: OrganizationInvitationWriter

    async def execute(self, command: AcceptOrganizationInvitationCommand) -> OrganizationMembership:
        logger.info(
            "organization.invitation.accept.started",
            extra={
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
                "has_token": bool(command.raw_token),
            },
        )
        if not _is_usable_token(command.raw_token):
            logger.warning(
                "organization.invitation.accept.invalid_token_shape",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        now = self.clock.now()
        invitation = await self.invitations.find_pending_by_token_hash(
            token_hash=self.token_hasher.hash(command.raw_token), now=now
        )
        if (
            invitation is None
            or invitation.status_at(now) is not OrganizationInvitationStatus.PENDING
        ):
            logger.warning(
                "organization.invitation.accept.rejected_token",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        invited_user_id = await self.user_emails.find_active_user_id_by_email_lookup_hash(
            email_lookup_hash=invitation.email_lookup_hash
        )
        if invited_user_id != command.actor_id:
            logger.warning(
                "organization.invitation.accept.rejected_identity",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(invitation.organization_id),
                    "invitation_id": str(invitation.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "organization.invitation.accept.rejected_inactive_user",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(invitation.organization_id),
                    "invitation_id": str(invitation.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        existing = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=invitation.organization_id
        )
        if existing is not None:
            logger.warning(
                "organization.invitation.accept.rejected_existing_member",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(invitation.organization_id),
                    "invitation_id": str(invitation.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        membership = OrganizationMembership(
            id=self.identifiers.new(),
            actor_id=command.actor_id,
            organization_id=invitation.organization_id,
            role=invitation.role,
            resource_scopes=_fresh_scope_ids(self.identifiers, invitation.resource_scopes),
        )
        accepted = await self.writer.accept(
            invitation=invitation,
            membership=membership,
            accepted_at=now,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=invitation.organization_id,
                action="organization.member.invitation.accepted",
                resource_type="organization_invitation",
                resource_id=str(invitation.id),
                result="succeeded",
            ),
        )
        if not accepted:
            logger.warning(
                "organization.invitation.accept.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(invitation.organization_id),
                    "invitation_id": str(invitation.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        logger.info(
            "organization.invitation.accept.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(invitation.organization_id),
                "invitation_id": str(invitation.id),
                "membership_id": str(membership.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return membership


def _fresh_scope_ids(
    identifiers: IdentifierGenerator, scopes: frozenset[MembershipResourceScope]
) -> frozenset[MembershipResourceScope]:
    return frozenset(
        MembershipResourceScope(id=identifiers.new(), resource=scope.resource, action=scope.action)
        for scope in scopes
    )


def _is_usable_token(token: str) -> bool:
    if not token or len(token) > 4096:
        return False
    return not any(character.isspace() for character in token)
