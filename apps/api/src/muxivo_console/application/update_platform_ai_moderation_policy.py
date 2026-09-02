"""Safely update one connected platform's AI moderation policy."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import (
    AuditEventWriter,
    IdentifierGenerator,
    OrganizationAuthorizer,
    PlatformAiModerationPolicyWriter,
    PlatformConnectionReader,
)
from muxivo_console.application.require_recent_authentication import RequireRecentAuthentication
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.ai_moderation_policy import PlatformAiModerationPolicy
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus


@dataclass(slots=True)
class UpdatePlatformAiModerationPolicy:
    """Coordinates Console authorization, assurance, platform command and audit fact."""

    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    policies: PlatformAiModerationPolicyWriter
    recent_authentication: RequireRecentAuthentication
    identifiers: IdentifierGenerator
    audit_events: AuditEventWriter

    async def execute(
        self,
        *,
        principal: BrowserSessionPrincipal,
        organization_id: UUID,
        connection_id: UUID,
        policy: PlatformAiModerationPolicy,
        correlation_id: UUID,
    ) -> PlatformAiModerationSummary:
        self.recent_authentication.check(principal)
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                principal.user_id,
                organization_id,
                AuthorizationResource.CONTROL_MODULES,
                AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to update AI moderation policy.")
        connection = await self.connections.find_for_organization(
            organization_id=organization_id, connection_id=connection_id
        )
        if (
            connection is None
            or connection.platform is not Platform.DISCORD
            or policy.platform is not connection.platform
            or connection.status is not ConnectionStatus.ACTIVE
        ):
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        try:
            summary = await self.policies.update_ai_moderation_policy_for_connection(
                organization_id=organization_id,
                actor_id=principal.user_id,
                external_resource_id=connection.external_resource_id,
                policy=policy,
                correlation_id=correlation_id,
            )
        except Exception:
            await self._record_audit(
                principal=principal,
                organization_id=organization_id,
                connection_id=connection_id,
                correlation_id=correlation_id,
                result="failed",
            )
            raise
        await self._record_audit(
            principal=principal,
            organization_id=organization_id,
            connection_id=connection_id,
            correlation_id=correlation_id,
            result="succeeded",
        )
        return summary

    async def _record_audit(
        self,
        *,
        principal: BrowserSessionPrincipal,
        organization_id: UUID,
        connection_id: UUID,
        correlation_id: UUID,
        result: str,
    ) -> None:
        await self.audit_events.record(
            AuditEvent(
                id=self.identifiers.new(),
                correlation_id=correlation_id,
                actor_id=principal.user_id,
                organization_id=organization_id,
                action="platform_ai_moderation_policy.updated",
                resource_type="platform_connection",
                resource_id=str(connection_id),
                result=result,
            )
        )
