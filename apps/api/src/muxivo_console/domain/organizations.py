"""Organization membership and scope rules owned by the Console domain."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)


class OrganizationRole(StrEnum):
    """Console roles; these are deliberately not Discord-native roles."""

    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    ANALYST = "analyst"
    VIEWER = "viewer"

    def may_assign(self, target: "OrganizationRole") -> bool:
        """Return whether this role can grant a strictly less privileged role."""
        return _ROLE_RANK[self] < _ROLE_RANK[target]


_ROLE_RANK = {
    OrganizationRole.OWNER: 0,
    OrganizationRole.ADMIN: 1,
    OrganizationRole.MODERATOR: 2,
    OrganizationRole.ANALYST: 3,
    OrganizationRole.VIEWER: 4,
}


@dataclass(frozen=True, slots=True)
class Organization:
    """A Console tenant that owns adapter connections and scoped settings."""

    id: UUID
    name: str
    slug: str

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 128:
            raise ValueError("Organization name must contain 1 to 128 non-blank characters.")
        if not self.slug or len(self.slug) > 96:
            raise ValueError("Organization slug must contain 1 to 96 characters.")


@dataclass(frozen=True, slots=True)
class OrganizationAccess:
    """A tenant the actor may enter, paired with the actor's Console role."""

    organization: Organization
    role: OrganizationRole


@dataclass(frozen=True, slots=True)
class OrganizationMember:
    """Non-secret Console-owned projection of one tenant membership."""

    membership_id: UUID
    user_id: UUID
    display_name: str
    role: OrganizationRole

    def __post_init__(self) -> None:
        if not self.display_name.strip() or len(self.display_name) > 64:
            raise ValueError("Member display name must contain 1 to 64 non-blank characters.")


@dataclass(frozen=True, slots=True)
class MembershipResourceScope:
    """An explicit grant to one platform-neutral Console resource/action pair."""

    resource: AuthorizationResource
    action: AuthorizationAction

    def allows(self, request: AuthorizationRequest) -> bool:
        return self.resource is request.resource and self.action is request.action


@dataclass(frozen=True, slots=True)
class OrganizationMembership:
    """A person's role and explicitly granted Console resource scopes."""

    actor_id: UUID
    organization_id: UUID
    role: OrganizationRole
    resource_scopes: frozenset[MembershipResourceScope] = frozenset()
    id: UUID | None = None

    def allows(self, request: AuthorizationRequest) -> bool:
        """Evaluate a policy request without consulting a platform service."""
        if request.actor_id != self.actor_id or request.organization_id != self.organization_id:
            return False
        if not _role_supports(self.role, request):
            return False
        if self.role is OrganizationRole.OWNER:
            return True
        return any(scope.allows(request) for scope in self.resource_scopes)


def _role_supports(role: OrganizationRole, request: AuthorizationRequest) -> bool:
    """Return the maximum capability of a role before its scopes narrow it."""
    if request.resource is AuthorizationResource.CONTROL_MODULES:
        return request.action is AuthorizationAction.READ
    if request.resource is AuthorizationResource.PLATFORM_CONNECTIONS:
        return role is OrganizationRole.ADMIN and request.action in {
            AuthorizationAction.READ,
            AuthorizationAction.MANAGE,
        }
    if request.resource is AuthorizationResource.ORGANIZATION_MEMBERSHIPS:
        return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN} and request.action in {
            AuthorizationAction.READ,
            AuthorizationAction.MANAGE,
        }
    return False
