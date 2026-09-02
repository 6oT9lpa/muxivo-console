"""Domain model for one-time organization membership invitations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole


class OrganizationInvitationStatus(StrEnum):
    """Externally visible state of an organization invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OrganizationInvitationDeliveryStatus(StrEnum):
    """State of the out-of-band invitation delivery attempt."""

    SENT = "sent"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OrganizationInvitation:
    """A pending membership offer without a plaintext e-mail or token."""

    id: UUID
    organization_id: UUID
    invited_by_user_id: UUID
    email_lookup_hash: str
    email_hint: str
    email_ciphertext: bytes
    token_hash: str
    role: OrganizationRole
    resource_scopes: frozenset[MembershipResourceScope]
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    delivery_status: OrganizationInvitationDeliveryStatus | None = None

    def __post_init__(self) -> None:
        if len(self.email_lookup_hash) != 64:
            raise ValueError("Invitation e-mail lookup hash must be a SHA-256 hex digest.")
        if len(self.token_hash) != 64:
            raise ValueError("Invitation token hash must be a SHA-256 hex digest.")
        if not self.email_hint.strip() or len(self.email_hint) > 192:
            raise ValueError("Invitation e-mail hint must contain 1 to 192 characters.")
        if not self.email_ciphertext:
            raise ValueError("Invitation e-mail ciphertext must not be empty.")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Invitation timestamps must be timezone-aware.")
        if self.expires_at <= self.created_at:
            raise ValueError("Invitation expiry must be after creation.")
        if self.accepted_at is not None and self.revoked_at is not None:
            raise ValueError("Invitation cannot be accepted and revoked at the same time.")
        if self.delivery_status is not None and not isinstance(
            self.delivery_status, OrganizationInvitationDeliveryStatus
        ):
            raise ValueError("Invitation delivery status is not supported.")

    def status_at(self, now: datetime) -> OrganizationInvitationStatus:
        """Resolve state at a supplied UTC instant without relying on process time."""
        if now.tzinfo is None:
            raise ValueError("Invitation status checks require a timezone-aware timestamp.")
        if self.accepted_at is not None:
            return OrganizationInvitationStatus.ACCEPTED
        if self.revoked_at is not None:
            return OrganizationInvitationStatus.REVOKED
        if self.expires_at <= now:
            return OrganizationInvitationStatus.EXPIRED
        return OrganizationInvitationStatus.PENDING
