"""Result returned after an invitation is persisted and delivery is attempted."""

from dataclasses import dataclass

from muxivo_console.domain.organization_invitations import OrganizationInvitation


@dataclass(frozen=True, slots=True)
class OrganizationInvitationCreationResult:
    """Expose invitation metadata together with its durable delivery status."""

    invitation: OrganizationInvitation
    delivery_status: str
