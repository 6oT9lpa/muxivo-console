"""Read generic channels from exactly one Console-owned platform connection."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformChannelCatalogReader,
    PlatformConnectionReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.channels import PlatformChannelCatalog
from muxivo_console.domain.connections import ConnectionStatus


@dataclass(slots=True)
class ListPlatformConnectionChannels:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    channel_catalogs: Mapping[Platform, PlatformChannelCatalogReader]

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
    ) -> PlatformChannelCatalog:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view platform channels.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if connection is None or connection.status not in {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
        }:
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        channel_catalog = self.channel_catalogs.get(connection.platform)
        if channel_catalog is None:
            raise PlatformHealthUnavailableError("No channel catalog adapter is available.")
        return await channel_catalog.get_channel_catalog_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
