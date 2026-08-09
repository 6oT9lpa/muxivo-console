from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import ModuleCatalog, OrganizationAuthorizer
from muxivo_console.domain.activity import ControlModule
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)


class AccessDeniedError(PermissionError):
    """Raised when a session actor cannot access an organization resource."""


class PlatformControlUnavailableError(RuntimeError):
    """Raised when an authorized platform Control API is unavailable or invalid."""


@dataclass(slots=True)
class ListControlModules:
    authorizer: OrganizationAuthorizer
    catalog: ModuleCatalog

    async def execute(
        self, *, actor_id: UUID, organization_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view this organization.")
        return await self.catalog.list_for_organization(
            actor_id=actor_id, organization_id=organization_id, correlation_id=correlation_id
        )
