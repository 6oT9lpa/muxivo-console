"""Command for creating a Console organization."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateOrganizationCommand:
    """Identify the actor and requested organization name."""

    actor_id: UUID
    name: str
    correlation_id: UUID
