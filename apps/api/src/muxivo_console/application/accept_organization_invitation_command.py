"""Command for accepting an organization invitation."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AcceptOrganizationInvitationCommand:
    """Carry the actor and one-time token without exposing the token in repr."""

    actor_id: UUID
    raw_token: str = field(repr=False)
    correlation_id: UUID
