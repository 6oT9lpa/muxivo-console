"""Command for listing organizations available to a user."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListOrganizationsCommand:
    """Identify the actor requesting the organization switcher data."""

    actor_id: UUID
    correlation_id: UUID
