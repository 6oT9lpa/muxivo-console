"""Command for revoking an organization invitation."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RevokeOrganizationInvitationCommand:
    """Identify the actor, organization and pending invitation."""

    actor_id: UUID
    organization_id: UUID
    invitation_id: UUID
    correlation_id: UUID
