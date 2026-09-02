"""Command for listing organization invitations."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListOrganizationInvitationsCommand:
    """Identify the organization and actor requesting its invitation list."""

    actor_id: UUID
    organization_id: UUID
    correlation_id: UUID
