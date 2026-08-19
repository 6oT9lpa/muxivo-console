"""Read one connected platform's effective AI moderation policy."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformAiModerationPolicyReader,
    PlatformConnectionReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation_policy import PlatformAiModerationPolicyState
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus


@dataclass(slots=True)
class GetPlatformAiModerationPolicy:
    """Read a complete editable policy after Console and native authority checks."""

    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    policies: PlatformAiModerationPolicyReader

    async def execute(
        self, *, actor_id: UUID, organization_id: UUID, connection_id: UUID, correlation_id: UUID
    ) -> PlatformAiModerationPolicyState:
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view AI moderation policy.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if (
            connection is None
            or connection.platform is not Platform.DISCORD
            or connection.status not in {ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}
        ):
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        return await self.policies.get_ai_moderation_policy_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=connection.external_resource_id,
            correlation_id=correlation_id,
        )
