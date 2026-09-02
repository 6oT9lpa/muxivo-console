"""Command for removing an organization member."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RemoveOrganizationMemberCommand:
    """Identify the actor, organization and target member."""

    actor_id: UUID
    organization_id: UUID
    user_id: UUID
    correlation_id: UUID
