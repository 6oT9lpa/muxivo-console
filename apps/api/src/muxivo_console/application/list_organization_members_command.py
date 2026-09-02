"""Command for listing organization members."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListOrganizationMembersCommand:
    """Identify the organization membership list requested by an actor."""

    actor_id: UUID
    organization_id: UUID
    correlation_id: UUID
