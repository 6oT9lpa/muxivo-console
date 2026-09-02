"""Update welcome settings only for an authorized, usable Discord connection."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionReader,
    PlatformWelcomeSettingsWriter,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.welcome import PlatformWelcomeSettings


@dataclass(slots=True)
class UpdatePlatformWelcomeSettings:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    welcome_settings: PlatformWelcomeSettingsWriter

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        settings: PlatformWelcomeSettings,
        correlation_id: UUID,
    ) -> PlatformWelcomeSettings:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to update welcome settings.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if (
            connection is None
            or connection.platform is not Platform.DISCORD
            or settings.platform is not connection.platform
            or connection.status is not ConnectionStatus.ACTIVE
        ):
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        return await self.welcome_settings.update_welcome_settings_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            settings=settings,
            correlation_id=correlation_id,
        )
