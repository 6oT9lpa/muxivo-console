"""Command for listing the authenticated user's login identities."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListLoginIdentitiesCommand:
    """Identify the actor whose first-party login identities are requested."""

    actor_id: UUID
    correlation_id: UUID
