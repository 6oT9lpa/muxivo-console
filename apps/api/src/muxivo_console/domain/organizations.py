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
    if request.resource is not AuthorizationResource.CONTROL_MODULES:
        return False
    return request.action is AuthorizationAction.READ
