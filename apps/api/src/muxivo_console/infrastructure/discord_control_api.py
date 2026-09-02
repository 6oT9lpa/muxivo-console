"""Discord Control API adapter, isolated from Discord runtime persistence."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import Clock, LoginIdentityReader
from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.ai_moderation_policy import (
    AiModerationAction,
    AiModerationEnforcementMode,
    AiModerationLabelRule,
    PlatformAiModerationPolicy,
    PlatformAiModerationPolicyState,
)
from muxivo_console.domain.audit_timeline import (
    PlatformAuditTimeline,
    PlatformAuditTimelineEvent,
)
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.bot_settings import PlatformBotSettings
from muxivo_console.domain.channel_purposes import ChannelPurpose, PlatformChannelPurposes
from muxivo_console.domain.channels import ChannelKind, PlatformChannel, PlatformChannelCatalog
from muxivo_console.domain.connection_reconciliation import (
    ConnectionReconciliationDecision,
    ConnectionReconciliationReason,
)
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.integrations import IntegrationSourceCount, PlatformIntegrations
from muxivo_console.domain.server_statistics import PlatformServerStatistics
from muxivo_console.domain.welcome import PlatformWelcomeSettings


@dataclass(frozen=True, slots=True)
class HmacControlAssertionIssuer:
    """Issues short-lived, audience-bound service assertions for one Control API."""

    issuer: str
    audience: str
    signing_key: bytes
    clock: Clock
    lifetime: timedelta = timedelta(seconds=60)

    def __post_init__(self) -> None:
        if len(self.signing_key) < 32:
            raise ValueError("Control assertion signing key must be at least 32 bytes.")
        if not self.issuer or not self.audience:
            raise ValueError("Control assertion issuer and audience must be non-empty.")

    def issue(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        resource: AuthorizationResource,
        action: AuthorizationAction,
        correlation_id: UUID,
        platform_subject: str | None = None,
        platform_resource_id: str | None = None,
    ) -> str:
        now = self.clock.now().astimezone(UTC)
        header = {"alg": "HS256", "typ": "JWT"}
        claims = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": str(actor_id),
            "organization_id": str(organization_id),
            "resource": resource.value,
            "action": action.value,
            "correlation_id": str(correlation_id),
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + self.lifetime).timestamp()),
        }
        if platform_subject is not None:
            claims["platform_subject"] = platform_subject
        if platform_resource_id is not None:
            if not platform_resource_id.strip() or len(platform_resource_id) > 255:
                raise ValueError("Platform resource identifier must contain 1 to 255 characters.")
            claims["platform_resource_id"] = platform_resource_id
        encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
        encoded_claims = _base64url(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
        signature = hmac.new(self.signing_key, signing_input, hashlib.sha256).digest()
        return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


@dataclass(frozen=True, slots=True)
class DiscordControlApiCatalog:
    """Maps Discord's versioned control response to Console's neutral module model."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False
    identities: LoginIdentityReader | None = None

    def __post_init__(self) -> None:
        _validate_control_base_url(self.base_url, self.allow_insecure_http)

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> tuple[ControlModule, ...]:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/modules",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError("Discord Control API request failed.") from error
        return _parse_discord_modules(payload)

    async def get_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/health",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API health request failed."
            ) from error
        return _parse_discord_health(payload)

    async def get_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/dashboard",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API dashboard request failed."
            ) from error
        return _parse_discord_dashboard(payload)

    async def get_bot_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformBotSettings:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=platform_subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/bot-settings",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API bot settings request failed."
            ) from error
        return _parse_discord_bot_settings(payload)

    async def get_integrations_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformIntegrations:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/integrations",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API integrations request failed."
            ) from error
        return _parse_discord_integrations(payload)

    async def get_server_statistics_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformServerStatistics:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        subject = await self.identities.find_provider_subject(
            user_id=actor_id,
            provider=LoginIdentityProvider.DISCORD,
        )
        if subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/"
                    f"{external_resource_id}/server-stats",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API server statistics request failed."
            ) from error
        return _parse_discord_server_statistics(payload)

    async def get_audit_timeline_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAuditTimeline:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        subject = await self.identities.find_provider_subject(
            user_id=actor_id,
            provider=LoginIdentityProvider.DISCORD,
        )
        if subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/"
                    f"{external_resource_id}/audit-timeline",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API audit timeline request failed."
            ) from error
        return _parse_discord_audit_timeline(payload)

    async def get_channel_catalog_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelCatalog:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/channels",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API channel catalog request failed."
            ) from error
        return _parse_discord_channel_catalog(payload)

    async def get_channel_purposes_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelPurposes:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/channel-purposes",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API channel purposes request failed."
            ) from error
        return _parse_discord_channel_purposes(payload)

    async def get_ai_moderation_summary_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAiModerationSummary:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/ai-moderation-summary",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API AI moderation summary request failed."
            ) from error
        return _parse_discord_ai_moderation_summary(payload)

    async def update_channel_purpose_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        purpose: ChannelPurpose,
        channel_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelPurposes:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        parsed_channel_id = _discord_snowflake_or_none(channel_id)
        if subject is None or parsed_channel_id is None:
            raise PlatformControlUnavailableError(
                "A linked Discord identity and channel are required."
            )
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.put(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/channel-purposes",
                    headers={"Authorization": f"Bearer {assertion}"},
                    json={
                        "purpose": purpose.value,
                        "channel_id": parsed_channel_id,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API channel purpose update failed."
            ) from error
        return _parse_discord_channel_purposes(payload)

    async def update_ai_moderation_policy_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        policy: PlatformAiModerationPolicy,
        correlation_id: UUID,
    ) -> PlatformAiModerationSummary:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        try:
            policy_payload = _discord_ai_moderation_policy_payload(policy)
            assertion = self.assertions.issue(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
                correlation_id=correlation_id,
                platform_subject=platform_subject,
                platform_resource_id=external_resource_id,
            )
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.put(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/ai-moderation-policy",
                    headers={"Authorization": f"Bearer {assertion}"},
                    json={"policy": policy_payload},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API AI moderation policy update failed."
            ) from error
        return _parse_discord_ai_moderation_summary(payload)

    async def get_ai_moderation_policy_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAiModerationPolicyState:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        try:
            assertion = self.assertions.issue(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
                correlation_id=correlation_id,
                platform_subject=platform_subject,
                platform_resource_id=external_resource_id,
            )
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/ai-moderation-policy",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API AI moderation policy request failed."
            ) from error
        return _parse_discord_ai_moderation_policy(payload)

    async def get_welcome_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformWelcomeSettings:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/welcome-settings",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API welcome settings request failed."
            ) from error
        return _parse_discord_welcome_settings(payload)

    async def update_welcome_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        settings: PlatformWelcomeSettings,
        correlation_id: UUID,
    ) -> PlatformWelcomeSettings:
        if self.identities is None:
            raise PlatformControlUnavailableError("Discord identity verification is unavailable.")
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            raise PlatformControlUnavailableError("A linked Discord identity is required.")
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_subject=platform_subject,
            platform_resource_id=external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout, transport=self.transport
            ) as client:
                response = await client.put(
                    f"/control/v1/organizations/{organization_id}/connections/{external_resource_id}/welcome-settings",
                    headers={"Authorization": f"Bearer {assertion}"},
                    json=_welcome_settings_payload(settings),
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API welcome settings update failed."
            ) from error
        return _parse_discord_welcome_settings(payload)


@dataclass(frozen=True, slots=True)
class DiscordPlatformConnectionVerifier:
    """Ask Discord to re-check native authority before Console links a guild."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    identities: LoginIdentityReader
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_control_base_url(self.base_url, self.allow_insecure_http)

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        if platform is not Platform.DISCORD:
            return False
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            return False
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.PLATFORM_CONNECTIONS,
            action=AuthorizationAction.MANAGE,
            correlation_id=correlation_id,
            platform_subject=platform_subject,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"/control/v1/organizations/{organization_id}/connections/verify",
                    headers={"Authorization": f"Bearer {assertion}"},
                    json={"platform": platform.value, "external_resource_id": external_resource_id},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API connection verification failed."
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("verified"), bool):
            raise PlatformControlUnavailableError(
                "Discord Control API returned an invalid connection verification payload."
            )
        return payload["verified"]


@dataclass(frozen=True, slots=True)
class DiscordPlatformConnectionReconciliationProbe:
    """Ask Discord Control API for a secret-free lifecycle reconciliation decision."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    system_actor_id: UUID
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_control_base_url(self.base_url, self.allow_insecure_http)

    async def inspect_connection(
        self, *, connection: PlatformConnection, correlation_id: UUID
    ) -> ConnectionReconciliationDecision:
        if connection.platform is not Platform.DISCORD:
            return ConnectionReconciliationDecision(
                target_status=connection.status,
                reason=ConnectionReconciliationReason.HEALTHY,
            )
        assertion = self.assertions.issue(
            actor_id=self.system_actor_id,
            organization_id=connection.organization_id,
            resource=AuthorizationResource.PLATFORM_CONNECTIONS,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=connection.external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    "/control/v1/organizations/"
                    f"{connection.organization_id}/connections/"
                    f"{connection.external_resource_id}/reconciliation",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API connection reconciliation request failed."
            ) from error
        return _parse_connection_reconciliation_decision(payload)


def _parse_discord_modules(payload: Any) -> tuple[ControlModule, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid module payload."
        )
    modules: list[ControlModule] = []
    try:
        for item in payload["items"]:
            if not isinstance(item, dict):
                raise ValueError("Module item must be an object.")
            if not all(
                isinstance(item.get(field), str)
                for field in ("key", "display_name", "platform", "capability", "status")
            ):
                raise ValueError("Module fields must be strings.")
            module = ControlModule(
                key=item["key"],
                display_name=item["display_name"],
                platform=Platform(item["platform"]),
                capability=ModuleCapability(item["capability"]),
                status=ModuleStatus(item["status"]),
            )
            if module.platform is not Platform.DISCORD:
                raise ValueError("Discord adapter cannot return another platform's module.")
            modules.append(module)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid module."
        ) from error
    return tuple(modules)


def _parse_discord_health(payload: Any) -> PlatformHealth:
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid health payload."
        )
    signals: list[HealthSignal] = []
    try:
        for item in payload["signals"]:
            if not isinstance(item, dict):
                raise ValueError("Health signal must be an object.")
            name, value, status = item["name"], item["value"], item["status"]
            latency_ms = item.get("latency_ms")
            if (
                not isinstance(name, str)
                or not isinstance(value, str)
                or not isinstance(status, str)
            ):
                raise ValueError("Health signal fields must be strings.")
            if latency_ms is not None and (
                not isinstance(latency_ms, int) or isinstance(latency_ms, bool)
            ):
                raise ValueError("Health signal latency must be an integer.")
            signals.append(
                HealthSignal(
                    key=_health_signal_key(name),
                    display_name=name,
                    value=value,
                    status=HealthStatus(status),
                    latency_ms=latency_ms,
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid health signal."
        ) from error
    return PlatformHealth(platform=Platform.DISCORD, signals=tuple(signals))


def _parse_connection_reconciliation_decision(
    payload: Any,
) -> ConnectionReconciliationDecision:
    if not isinstance(payload, dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid connection reconciliation payload."
        )
    try:
        target_status = payload["target_status"]
        reason = payload["reason"]
        if not isinstance(target_status, str) or not isinstance(reason, str):
            raise ValueError("Connection reconciliation fields must be strings.")
        return ConnectionReconciliationDecision(
            target_status=ConnectionStatus(target_status),
            reason=ConnectionReconciliationReason(reason),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid connection reconciliation decision."
        ) from error


def _parse_discord_dashboard(payload: Any) -> PlatformDashboardSummary:
    if not isinstance(payload, dict) or not isinstance(payload.get("metrics"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid dashboard payload."
        )
    metrics = payload["metrics"]
    try:
        counters = tuple(
            metrics[field] for field in ("messages_today", "ai_flagged_today", "creator_sources")
        )
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in counters):
            raise ValueError("Dashboard counter must be an integer.")
        latency = metrics.get("bot_latency_ms")
        if latency is not None and (not isinstance(latency, int) or isinstance(latency, bool)):
            raise ValueError("Dashboard latency must be an integer.")
        return PlatformDashboardSummary(
            platform=Platform.DISCORD,
            messages_today=counters[0],
            ai_flagged_today=counters[1],
            creator_sources=counters[2],
            bot_latency_ms=latency,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid dashboard summary."
        ) from error


def _parse_discord_server_statistics(payload: Any) -> PlatformServerStatistics:
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid server statistics payload."
        )
    summary = payload["summary"]
    fields = (
        "period_days",
        "total_messages",
        "active_users",
        "active_channels",
        "current_member_count",
        "total_voice_minutes",
        "joins",
        "leaves",
        "moderation_events",
    )
    try:
        values = {field: summary[field] for field in fields}
        if not all(
            isinstance(value, int) and not isinstance(value, bool) for value in values.values()
        ):
            raise ValueError("Server statistic must be an integer.")
        return PlatformServerStatistics(platform=Platform.DISCORD, **values)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid aggregate server statistics."
        ) from error


def _parse_discord_audit_timeline(payload: Any) -> PlatformAuditTimeline:
    if not isinstance(payload, dict) or not isinstance(payload.get("timeline"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid audit timeline payload."
        )
    timeline = payload["timeline"]
    try:
        items = timeline["items"]
        limit = timeline["limit"]
        if not isinstance(items, list) or not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("Audit timeline fields are invalid.")
        events = tuple(
            PlatformAuditTimelineEvent(
                event_type=item["event_type"],
                occurred_at=item["occurred_at"],
            )
            for item in items
            if isinstance(item, dict)
        )
        if len(events) != len(items):
            raise ValueError("Audit timeline item must be an object.")
        return PlatformAuditTimeline(Platform.DISCORD, events, limit)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid sanitized audit timeline data."
        ) from error


def _parse_discord_bot_settings(payload: Any) -> PlatformBotSettings:
    if not isinstance(payload, dict) or not isinstance(payload.get("settings"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid bot settings payload."
        )
    settings = payload["settings"]
    try:
        tier = settings["subscription_tier"]
        enabled = settings["activity_rotation_enabled"]
        interval = settings["activity_rotation_interval_seconds"]
        retention = settings["retention"]
        if (
            not isinstance(tier, str)
            or not isinstance(enabled, bool)
            or not isinstance(interval, int)
            or isinstance(interval, bool)
            or not isinstance(retention, dict)
            or not all(
                isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
                for key, value in retention.items()
            )
        ):
            raise ValueError("Bot settings contain invalid fields.")
        return PlatformBotSettings(
            platform=Platform.DISCORD,
            subscription_tier=tier,
            activity_rotation_enabled=enabled,
            activity_rotation_interval_seconds=interval,
            retention_days=tuple(sorted(retention.items())),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid bot settings."
        ) from error


def _parse_discord_integrations(payload: Any) -> PlatformIntegrations:
    try:
        data = payload["integrations"]
        creator = data["creator_platforms"]
        sources = tuple(
            IntegrationSourceCount(
                str(item["platform"]), int(item["count"]), int(item["active_count"] or 0)
            )
            for item in creator["sources"]
        )
        return PlatformIntegrations(
            Platform.DISCORD,
            str(data["discord_bot"]["status"]),
            str(creator["status"]),
            int(creator["poll_interval_seconds"]),
            sources,
            str(data["muxivo_core"]["status"]),
            str(data["database"]["status"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid integrations."
        ) from error


def _parse_discord_channel_catalog(payload: Any) -> PlatformChannelCatalog:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid channel catalog payload."
        )
    try:
        channels = tuple(
            PlatformChannel(id=item["id"], name=item["name"], kind=ChannelKind(item["kind"]))
            for item in payload["items"]
            if isinstance(item, dict)
        )
        if len(channels) != len(payload["items"]):
            raise ValueError("Channel item must be an object.")
        return PlatformChannelCatalog(platform=Platform.DISCORD, items=channels)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid channel catalog."
        ) from error


def _parse_discord_channel_purposes(payload: Any) -> PlatformChannelPurposes:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid channel purposes payload."
        )
    try:
        assignments = {
            ChannelPurpose(purpose): channel_id for purpose, channel_id in payload["items"].items()
        }
        if not all(isinstance(channel_id, str) for channel_id in assignments.values()):
            raise ValueError("Channel purpose identifier must be a string.")
        return PlatformChannelPurposes(Platform.DISCORD, assignments)
    except (TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid channel purposes."
        ) from error


def _parse_discord_ai_moderation_summary(payload: Any) -> PlatformAiModerationSummary:
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid AI moderation summary."
        )
    summary = payload["summary"]
    try:
        return PlatformAiModerationSummary(
            platform=Platform.DISCORD,
            enforcement_mode=str(summary["enforcement_mode"]),
            test_mode=bool(summary["test_mode"]),
            is_default_policy=bool(summary["is_default_policy"]),
            covered_channel_count=int(summary["covered_channel_count"]),
            log_channel_configured=bool(summary["log_channel_configured"]),
            label_count=int(summary["label_count"]),
            blacklist_word_count=int(summary["blacklist_word_count"]),
            allowed_domain_count=int(summary["allowed_domain_count"]),
            automated_timeout_enabled=bool(summary["automated_timeout_enabled"]),
            automated_kick_enabled=bool(summary["automated_kick_enabled"]),
            automated_ban_enabled=bool(summary["automated_ban_enabled"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid AI moderation summary values."
        ) from error


def _parse_discord_welcome_settings(payload: Any) -> PlatformWelcomeSettings:
    if not isinstance(payload, dict) or not isinstance(payload.get("settings"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid welcome settings payload."
        )
    settings = payload["settings"]
    try:
        title, description = settings["title"], settings["description"]
        color, is_enabled = settings["color"], settings["is_enabled"]
        optional_strings = tuple(
            settings.get(field)
            for field in (
                "thumbnail_url",
                "footer_text",
                "footer_icon_url",
                "rules_channel_id",
                "roles_channel_id",
            )
        )
        if (
            not isinstance(title, str)
            or not isinstance(description, str)
            or not isinstance(color, int)
            or isinstance(color, bool)
            or not isinstance(is_enabled, bool)
            or not all(value is None or isinstance(value, str) for value in optional_strings)
        ):
            raise ValueError("Welcome settings contain invalid fields.")
        return PlatformWelcomeSettings(
            platform=Platform.DISCORD,
            title=title,
            description=description,
            thumbnail_url=optional_strings[0],
            footer_text=optional_strings[1],
            footer_icon_url=optional_strings[2],
            color=color,
            is_enabled=is_enabled,
            rules_channel_id=optional_strings[3],
            roles_channel_id=optional_strings[4],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid welcome settings."
        ) from error


def _welcome_settings_payload(settings: PlatformWelcomeSettings) -> dict[str, Any]:
    return {
        "title": settings.title,
        "description": settings.description,
        "thumbnail_url": settings.thumbnail_url,
        "footer_text": settings.footer_text,
        "footer_icon_url": settings.footer_icon_url,
        "color": settings.color,
        "is_enabled": settings.is_enabled,
        "rules_channel_id": _discord_snowflake_or_none(settings.rules_channel_id),
        "roles_channel_id": _discord_snowflake_or_none(settings.roles_channel_id),
    }


def _discord_ai_moderation_policy_payload(policy: PlatformAiModerationPolicy) -> dict[str, Any]:
    if policy.platform is not Platform.DISCORD:
        raise ValueError("AI moderation policy must target Discord.")
    return {
        "blacklist_words": list(policy.blacklist_words),
        "allowed_domains": list(policy.allowed_domains),
        "labels": {
            label: {
                "risk_threshold": rule.risk_threshold,
                "min_action": rule.min_action.value,
                "max_action": rule.max_action.value,
            }
            for label, rule in policy.labels.items()
        },
        "blacklist_action": policy.blacklist_action.value,
        "unapproved_domain_action": policy.unapproved_domain_action.value,
        "context_window_days": policy.context_window_days,
        "repeat_offender_threshold": policy.repeat_offender_threshold,
        "repeat_offender_action": policy.repeat_offender_action.value,
        "escalation_enabled": policy.escalation_enabled,
        "escalation_score_threshold": policy.escalation_score_threshold,
        "escalation_half_life_days": policy.escalation_half_life_days,
        "excluded_user_ids": _discord_snowflakes(policy.excluded_user_ids),
        "excluded_role_ids": _discord_snowflakes(policy.excluded_role_ids),
        "excluded_channel_ids": _discord_snowflakes(policy.excluded_channel_ids),
        "exclude_bots": policy.exclude_bots,
        "ocr_enabled": policy.ocr_enabled,
        "ocr_failure_mode": policy.ocr_failure_mode,
        "ocr_max_gif_frames": policy.ocr_max_gif_frames,
        "ocr_process_empty_result": policy.ocr_process_empty_result,
        "test_mode": policy.test_mode,
        "enforcement_mode": policy.enforcement_mode.value,
        "limited_min_confidence": policy.limited_min_confidence,
        "limited_hard_rule_labels": list(policy.limited_hard_rule_labels),
        "beta_enforcement_acknowledged": policy.beta_enforcement_acknowledged,
        "allow_automated_timeout": policy.allow_automated_timeout,
        "allow_automated_kick": policy.allow_automated_kick,
        "allow_automated_ban": policy.allow_automated_ban,
    }


def _parse_discord_ai_moderation_policy(payload: Any) -> PlatformAiModerationPolicyState:
    if not isinstance(payload, dict) or not isinstance(payload.get("policy"), dict):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid AI moderation policy."
        )
    policy = payload["policy"]
    try:
        labels_payload = policy["labels"]
        if not isinstance(labels_payload, dict):
            raise ValueError("AI moderation labels must be an object.")
        labels = {
            str(label): AiModerationLabelRule(
                risk_threshold=float(rule["risk_threshold"]),
                min_action=AiModerationAction(rule["min_action"]),
                max_action=AiModerationAction(rule["max_action"]),
            )
            for label, rule in labels_payload.items()
            if isinstance(rule, dict)
        }
        if len(labels) != len(labels_payload):
            raise ValueError("AI moderation label must be an object.")
        return PlatformAiModerationPolicyState(
            policy=PlatformAiModerationPolicy(
                platform=Platform.DISCORD,
                blacklist_words=_string_tuple(policy["blacklist_words"]),
                allowed_domains=_string_tuple(policy["allowed_domains"]),
                labels=labels,
                blacklist_action=AiModerationAction(policy["blacklist_action"]),
                unapproved_domain_action=AiModerationAction(policy["unapproved_domain_action"]),
                context_window_days=int(policy["context_window_days"]),
                repeat_offender_threshold=int(policy["repeat_offender_threshold"]),
                repeat_offender_action=AiModerationAction(policy["repeat_offender_action"]),
                escalation_enabled=_required_bool(policy, "escalation_enabled"),
                escalation_score_threshold=float(policy["escalation_score_threshold"]),
                escalation_half_life_days=float(policy["escalation_half_life_days"]),
                excluded_user_ids=_string_tuple(policy["excluded_user_ids"]),
                excluded_role_ids=_string_tuple(policy["excluded_role_ids"]),
                excluded_channel_ids=_string_tuple(policy["excluded_channel_ids"]),
                exclude_bots=_required_bool(policy, "exclude_bots"),
                ocr_enabled=_required_bool(policy, "ocr_enabled"),
                ocr_failure_mode=str(policy["ocr_failure_mode"]),
                ocr_max_gif_frames=int(policy["ocr_max_gif_frames"]),
                ocr_process_empty_result=_required_bool(policy, "ocr_process_empty_result"),
                test_mode=_required_bool(policy, "test_mode"),
                enforcement_mode=AiModerationEnforcementMode(policy["enforcement_mode"]),
                limited_min_confidence=float(policy["limited_min_confidence"]),
                limited_hard_rule_labels=_string_tuple(policy["limited_hard_rule_labels"]),
                beta_enforcement_acknowledged=_required_bool(
                    policy, "beta_enforcement_acknowledged"
                ),
                allow_automated_timeout=_required_bool(policy, "allow_automated_timeout"),
                allow_automated_kick=_required_bool(policy, "allow_automated_kick"),
                allow_automated_ban=_required_bool(policy, "allow_automated_ban"),
            ),
            is_default_policy=_required_bool(payload, "is_default_policy"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned invalid AI moderation policy values."
        ) from error


def _string_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list) or not all(isinstance(value, (str, int)) for value in values):
        raise ValueError("Expected a list of identifiers or strings.")
    return tuple(str(value) for value in values)


def _required_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean.")
    return value


def _discord_snowflakes(values: tuple[str, ...]) -> list[int]:
    return [_discord_snowflake_or_none(value) for value in values]


def _discord_snowflake_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    if not value.isdecimal() or not 1 <= len(value) <= 20:
        raise ValueError("Discord channel identifier must be a snowflake.")
    return int(value)


def _health_signal_key(name: str) -> str:
    return "discord." + "".join(
        character.lower() if character.isalnum() else "-" for character in name
    ).strip("-")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _validate_control_base_url(base_url: str, allow_insecure_http: bool) -> None:
    parsed = urlparse(base_url)
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes or not parsed.netloc or parsed.username:
        raise ValueError("Discord Control API base URL must be an absolute service URL.")
