"""Platform routing boundary for independently deployed Control API adapters."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import ControlModule, Platform
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import PlatformHealth
from muxivo_console.domain.platforms import (
    PlatformAdapterCapability,
    PlatformAdapterDescriptor,
)
from muxivo_console.domain.server_stats import PlatformServerStats
from muxivo_console.infrastructure.discord_control_api import (
    DiscordControlApiCatalog,
    DiscordPlatformConnectionVerifier,
)
from muxivo_console.infrastructure.discord_server_stats_api import DiscordServerStatsApi


class PlatformControlAdapter(Protocol):
    """One platform-specific Control API facade hidden behind the registry."""

    platform: Platform
    capabilities: frozenset[PlatformAdapterCapability]

    async def list_modules(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]: ...

    async def get_health(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth: ...

    async def get_dashboard(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary: ...

    async def get_server_stats(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats: ...

    async def verify_connection(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool: ...


class DiscordPlatformControlAdapter:
    """Keeps Discord-specific HTTP and identity adapters separate from generic routing."""

    platform = Platform.DISCORD
    capabilities = frozenset(
        {
            PlatformAdapterCapability.CONNECTION_REGISTRATION,
            PlatformAdapterCapability.CONTROL_MODULES,
            PlatformAdapterCapability.HEALTH,
            PlatformAdapterCapability.DASHBOARD_SUMMARY,
            PlatformAdapterCapability.SERVER_STATS,
        }
    )

    def __init__(
        self,
        catalog: DiscordControlApiCatalog,
        verifier: DiscordPlatformConnectionVerifier,
    ) -> None:
        self._catalog = catalog
        self._verifier = verifier
        self._server_stats = DiscordServerStatsApi(
            base_url=catalog.base_url,
            assertions=catalog.assertions,
            timeout=catalog.timeout,
            transport=catalog.transport,
            allow_insecure_http=catalog.allow_insecure_http,
        )

    async def list_modules(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]:
        return await self._catalog.list_for_organization(
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

    async def get_health(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth:
        return await self._catalog.get_for_organization(
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

    async def get_dashboard(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary:
        return await self._catalog.get_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )

    async def get_server_stats(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats:
        return await self._server_stats.get_for_connection(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=external_resource_id,
            period_days=period_days,
            correlation_id=correlation_id,
        )

    async def verify_connection(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        return await self._verifier.verify_registration(
            actor_id=actor_id,
            organization_id=organization_id,
            platform=Platform.DISCORD,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )


class PlatformControlRegistry:
    """Dispatch application ports by platform without leaking adapter conditionals upward."""

    def __init__(self, adapters: Sequence[PlatformControlAdapter]) -> None:
        self._adapters: dict[Platform, PlatformControlAdapter] = {}
        for adapter in adapters:
            if adapter.platform in self._adapters:
                raise ValueError(f"Duplicate platform control adapter: {adapter.platform.value}")
            self._adapters[adapter.platform] = adapter

    @property
    def supported_platforms(self) -> tuple[Platform, ...]:
        return tuple(sorted(self._adapters, key=lambda platform: platform.value))

    def list_configured(self) -> tuple[PlatformAdapterDescriptor, ...]:
        """Describe deployment capabilities; this is not a user authorization decision."""
        return tuple(
            PlatformAdapterDescriptor(
                platform=platform,
                capabilities=self._adapters[platform].capabilities,
            )
            for platform in self.supported_platforms
        )

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]:
        modules: list[ControlModule] = []
        for platform in self.supported_platforms:
            modules.extend(
                await self._adapters[platform].list_modules(
                    organization_id=organization_id,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                )
            )
        return tuple(modules)

    async def get_for_organization(
        self,
        *,
        platform: Platform,
        organization_id: UUID,
        actor_id: UUID,
        correlation_id: UUID,
    ) -> PlatformHealth:
        return await self._require(platform).get_health(
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

    async def get_for_connection(
        self,
        *,
        platform: Platform,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary:
        return await self._require(platform).get_dashboard(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )

    async def get_server_stats_for_connection(
        self,
        *,
        platform: Platform,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        period_days: int,
        correlation_id: UUID,
    ) -> PlatformServerStats:
        return await self._require(platform).get_server_stats(
            organization_id=organization_id,
            actor_id=actor_id,
            external_resource_id=external_resource_id,
            period_days=period_days,
            correlation_id=correlation_id,
        )

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        adapter = self._adapters.get(platform)
        supports_registration = (
            adapter is not None
            and PlatformAdapterCapability.CONNECTION_REGISTRATION in adapter.capabilities
        )
        if not supports_registration or adapter is None:
            return False
        return await adapter.verify_connection(
            actor_id=actor_id,
            organization_id=organization_id,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )

    def _require(self, platform: Platform) -> PlatformControlAdapter:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise PlatformControlUnavailableError(
                f"No Control API adapter is configured for {platform.value}."
            )
        return adapter
