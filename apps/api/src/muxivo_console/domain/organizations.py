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

    def supports_scope(self, scope: "MembershipResourceScope") -> bool:
        """Return whether this role can ever use a resource scope grant."""
        return _role_supports_pair(self, scope.resource, scope.action)


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
class MembershipResourceScope:
    """An explicit grant to one platform-neutral Console resource/action pair."""

    resource: AuthorizationResource
    action: AuthorizationAction
    id: UUID | None = None

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
        # Owners are the organization-wide administrative authority.  Resolve
        # this before the role-specific capability matrix so a resource added
        # to the matrix cannot accidentally exclude the owner role.
        if self.role is OrganizationRole.OWNER:
            return True
        if not _role_supports(self.role, request):
            return False
        return any(scope.allows(request) for scope in self.resource_scopes)


@dataclass(frozen=True, slots=True)
class OrganizationMemberProfile:
    """Safe display projection for one organization member."""

    membership: OrganizationMembership
    display_name: str

    def __post_init__(self) -> None:
        if not self.display_name.strip() or len(self.display_name) > 64:
            raise ValueError("Organization member display name must contain 1 to 64 characters.")


@dataclass(frozen=True, slots=True)
class OrganizationMembershipProfile:
    """Organization plus the current actor's membership, used by the Console switcher."""

    organization: Organization
    membership: OrganizationMembership


def _role_supports(role: OrganizationRole, request: AuthorizationRequest) -> bool:
    """Return the maximum capability of a role before its scopes narrow it."""
    return _role_supports_pair(role, request.resource, request.action)


def _role_supports_pair(
    role: OrganizationRole, resource: AuthorizationResource, action: AuthorizationAction
) -> bool:
    if resource is AuthorizationResource.ORGANIZATION_MEMBERS:
        return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN}
    if resource is AuthorizationResource.CONTROL_MODULES:
        return action is AuthorizationAction.READ
    if resource is AuthorizationResource.PLATFORM_CONNECTIONS:
        return role is OrganizationRole.ADMIN and action in {
            AuthorizationAction.READ,
            AuthorizationAction.MANAGE,
        }
    if resource is AuthorizationResource.AUDIT_EVENTS:
        return role in {OrganizationRole.ADMIN, OrganizationRole.ANALYST} and (
            action is AuthorizationAction.READ
        )
    return False
