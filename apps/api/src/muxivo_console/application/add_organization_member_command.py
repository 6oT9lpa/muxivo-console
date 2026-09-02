"""Command for adding an existing Console user to an organization."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole


@dataclass(frozen=True, slots=True)
class AddOrganizationMemberCommand:
    """Describe the invited user's role and scoped permissions."""

    actor_id: UUID
    organization_id: UUID
    email: str
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID
