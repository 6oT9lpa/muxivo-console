"""Accept an organization invitation for the account owning the invited e-mail."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

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

logger = logging.getLogger(__name__)


class OrganizationInvitationAcceptanceRejectedError(PermissionError):
    """Safe failure for invalid, expired, consumed or mismatched invitations."""


@dataclass(frozen=True, slots=True)
class AcceptOrganizationInvitationCommand:
    actor_id: UUID
    raw_token: str
    correlation_id: UUID


@dataclass(slots=True)
class AcceptOrganizationInvitation:
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
            },
        )
        if not _is_usable_token(command.raw_token):
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
            raise OrganizationInvitationAcceptanceRejectedError("Invitation acceptance failed.")
        existing = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=invitation.organization_id
        )
        if existing is not None:
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
    return (
        bool(token) and len(token) <= 4096 and not any(character.isspace() for character in token)
    )
