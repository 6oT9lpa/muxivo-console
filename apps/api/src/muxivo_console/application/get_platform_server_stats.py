"""Read resource-bound server statistics through the selected platform adapter."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.application.ports import OrganizationAuthorizer, PlatformConnectionReader
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.server_stats import PlatformServerStats


class PlatformServerStatsReader(Protocol):
    async def get_server_stats_for_connection(
        self,
        *,
        platform: Platform,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats: ...


@dataclass(slots=True)
class GetPlatformServerStats:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    stats: PlatformServerStatsReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats:
        if not 1 <= period_days <= 365:
            raise ValueError("Server stats period must be between 1 and 365 days.")
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError(
                "The actor is not allowed to view platform server statistics."
            )
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if connection is None or connection.status not in {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
        }:
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        stats = await self.stats.get_server_stats_for_connection(
            platform=connection.platform,
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            period_days=period_days,
            correlation_id=correlation_id,
        )
        if stats.platform is not connection.platform:
            raise PlatformControlUnavailableError(
                "Platform server stats response does not match the selected connection."
            )
        return stats
