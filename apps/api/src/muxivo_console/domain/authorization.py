"""Platform-neutral authorization facts used at Console application boundaries.

The Console authorizes every request from facts it owns: who is acting, which
organization they selected, and the exact resource/action pair.  Platform
services must perform their own authorization after Console grants access.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AuthorizationAction(StrEnum):
    """Actions currently exposed by the Console control plane."""

    READ = "read"


class AuthorizationResource(StrEnum):
    """Platform-neutral Console resources, deliberately independent of guild IDs."""

    CONTROL_MODULES = "console.control_modules"


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """All facts required for one Console authorization decision."""

    actor_id: UUID
    organization_id: UUID
    resource: AuthorizationResource
    action: AuthorizationAction


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """A fail-closed policy result returned by an application port."""

    allowed: bool

    @classmethod
    def allow(cls) -> "AuthorizationDecision":
        return cls(allowed=True)

    @classmethod
    def deny(cls) -> "AuthorizationDecision":
        return cls(allowed=False)
