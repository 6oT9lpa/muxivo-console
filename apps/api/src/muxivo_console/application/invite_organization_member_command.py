"""Command for creating an organization membership invitation."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole


@dataclass(frozen=True, slots=True)
class InviteOrganizationMemberCommand:
    """Describe the invited address, role and resource scopes."""

    actor_id: UUID
    organization_id: UUID
    email: str
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID
