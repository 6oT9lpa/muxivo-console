"""Read aggregate server statistics through the connection's platform adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionReader,
    PlatformServerStatisticsReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.server_statistics import PlatformServerStatistics


@dataclass(slots=True)
class GetPlatformServerStatistics:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    readers: Mapping[Platform, PlatformServerStatisticsReader]

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
    ) -> PlatformServerStatistics:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view server statistics.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id,
            connection_id=connection_id,
        )
        if connection is None or connection.status not in {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
        }:
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        reader = self.readers.get(connection.platform)
        if reader is None:
            raise PlatformHealthUnavailableError("No server statistics adapter is available.")
        return await reader.get_server_statistics_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
