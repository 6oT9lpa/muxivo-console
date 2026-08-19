"""Read one connected platform's non-secret runtime settings."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformBotSettingsReader,
    PlatformConnectionReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.bot_settings import PlatformBotSettings
from muxivo_console.domain.connections import ConnectionStatus


@dataclass(slots=True)
class GetPlatformBotSettings:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    settings_readers: Mapping[Platform, PlatformBotSettingsReader]

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
    ) -> PlatformBotSettings:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view bot settings.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if connection is None or connection.status not in {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
        }:
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        settings_reader = self.settings_readers.get(connection.platform)
        if settings_reader is None:
            raise PlatformHealthUnavailableError("No bot settings adapter is available.")
        return await settings_reader.get_bot_settings_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
