"""Command for changing an organization member's role and scopes."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole


@dataclass(frozen=True, slots=True)
class UpdateOrganizationMemberCommand:
    """Describe the target membership and its replacement authorization policy."""

    actor_id: UUID
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID
