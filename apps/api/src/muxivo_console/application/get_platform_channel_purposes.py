"""Read channel purpose assignments for one usable Console connection."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformChannelPurposesReader,
    PlatformConnectionReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.channel_purposes import PlatformChannelPurposes
from muxivo_console.domain.connections import ConnectionStatus


@dataclass(slots=True)
class GetPlatformChannelPurposes:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    purposes: PlatformChannelPurposesReader

    async def execute(
        self, *, actor_id: UUID, organization_id: UUID, connection_id: UUID, correlation_id: UUID
    ) -> PlatformChannelPurposes:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view channel purposes.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if (
            connection is None
            or connection.platform is not Platform.DISCORD
            or connection.status not in {ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}
        ):
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        return await self.purposes.get_channel_purposes_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
