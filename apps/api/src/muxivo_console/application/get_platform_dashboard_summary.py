"""Read a resource-bound, non-sensitive dashboard summary from a platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionReader,
    PlatformDashboardReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.dashboard import PlatformDashboardSummary


@dataclass(slots=True)
class GetPlatformDashboardSummary:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    dashboards: Mapping[Platform, PlatformDashboardReader]

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary:
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
                "The actor is not allowed to view platform dashboard summaries."
            )
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if connection is None or connection.status not in {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
        }:
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        dashboard = self.dashboards.get(connection.platform)
        if dashboard is None:
            raise PlatformHealthUnavailableError("No dashboard adapter is available.")
        return await dashboard.get_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
