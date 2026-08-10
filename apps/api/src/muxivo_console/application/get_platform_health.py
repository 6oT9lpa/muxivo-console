"""Read aggregate platform health through the platform's Control API."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionReader,
    PlatformHealthReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.health import PlatformHealth


class PlatformHealthUnavailableError(RuntimeError):
    """The organization has no connection that may safely expose platform health."""


@dataclass(slots=True)
class GetPlatformHealth:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    health: PlatformHealthReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        correlation_id: UUID,
    ) -> PlatformHealth:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view platform health.")
        connections = await self.connections.list_for_organization(
            organization_id=organization_id, after_id=None, limit=100
        )
        if not any(
            connection.platform is platform
            and connection.status in {ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}
            for connection in connections
        ):
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        return await self.health.get_for_organization(
            platform=platform,
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
