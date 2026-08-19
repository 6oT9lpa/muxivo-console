from uuid import uuid4

import pytest
from muxivo_console.application.get_platform_dashboard_summary import (
    GetPlatformDashboardSummary,
)
from muxivo_console.application.get_platform_health import (
    GetPlatformHealth,
    PlatformHealthUnavailableError,
)
from muxivo_console.application.get_platform_server_statistics import (
    GetPlatformServerStatistics,
)
from muxivo_console.application.list_platform_connection_channels import (
    ListPlatformConnectionChannels,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationDecision
from muxivo_console.domain.channels import ChannelKind, PlatformChannel, PlatformChannelCatalog
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.domain.server_statistics import PlatformServerStatistics


class Authorizer:
    async def authorize(self, *_: object) -> AuthorizationDecision:
        return AuthorizationDecision.allow()


class Connections:
    def __init__(self, connection: PlatformConnection) -> None:
        self.connection = connection

    async def find_for_organization(self, **_: object) -> PlatformConnection:
        return self.connection

    async def list_for_organization(self, **_: object) -> tuple[PlatformConnection, ...]:
        return (self.connection,)


class TwitchAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_for_connection(self, **_: object) -> PlatformDashboardSummary:
        self.calls.append("dashboard")
        return PlatformDashboardSummary(Platform.TWITCH, 12, 1, 2, 40)

    async def get_channel_catalog_for_connection(self, **_: object) -> PlatformChannelCatalog:
        self.calls.append("channels")
        return PlatformChannelCatalog(
            Platform.TWITCH, (PlatformChannel("chat", "Chat", ChannelKind.TEXT),)
        )

    async def get_for_organization(self, **_: object) -> PlatformHealth:
        self.calls.append("health")
        return PlatformHealth(
            Platform.TWITCH,
            (HealthSignal("twitch.chat", "Chat", "Connected", HealthStatus.OPERATIONAL, 40),),
        )

    async def get_server_statistics_for_connection(self, **_: object) -> PlatformServerStatistics:
        self.calls.append("server-statistics")
        return PlatformServerStatistics(Platform.TWITCH, 7, 12, 4, 1, 20, 0, 1, 0, 0)


def connection() -> PlatformConnection:
    return PlatformConnection(
        uuid4(), uuid4(), Platform.TWITCH, "muxivo-live", ConnectionStatus.ACTIVE
    )


@pytest.mark.asyncio
async def test_dashboard_uses_the_adapter_registered_for_the_connection_platform() -> None:
    adapter, current = TwitchAdapter(), connection()
    result = await GetPlatformDashboardSummary(
        Authorizer(), Connections(current), {Platform.TWITCH: adapter}
    ).execute(
        actor_id=uuid4(),
        organization_id=current.organization_id,
        connection_id=current.id,
        correlation_id=uuid4(),
    )

    assert result.platform is Platform.TWITCH
    assert adapter.calls == ["dashboard"]


@pytest.mark.asyncio
async def test_channels_use_the_adapter_registered_for_the_connection_platform() -> None:
    adapter, current = TwitchAdapter(), connection()
    result = await ListPlatformConnectionChannels(
        Authorizer(), Connections(current), {Platform.TWITCH: adapter}
    ).execute(
        actor_id=uuid4(),
        organization_id=current.organization_id,
        connection_id=current.id,
        correlation_id=uuid4(),
    )

    assert result.platform is Platform.TWITCH
    assert adapter.calls == ["channels"]


@pytest.mark.asyncio
async def test_server_statistics_uses_the_adapter_registered_for_the_connection_platform() -> None:
    adapter, current = TwitchAdapter(), connection()
    result = await GetPlatformServerStatistics(
        Authorizer(), Connections(current), {Platform.TWITCH: adapter}
    ).execute(
        actor_id=uuid4(),
        organization_id=current.organization_id,
        connection_id=current.id,
        correlation_id=uuid4(),
    )

    assert result.platform is Platform.TWITCH
    assert adapter.calls == ["server-statistics"]


@pytest.mark.asyncio
async def test_health_uses_the_adapter_registered_for_the_requested_platform() -> None:
    adapter, current = TwitchAdapter(), connection()
    result = await GetPlatformHealth(
        Authorizer(), Connections(current), {Platform.TWITCH: adapter}
    ).execute(
        actor_id=uuid4(),
        organization_id=current.organization_id,
        platform=Platform.TWITCH,
        correlation_id=uuid4(),
    )

    assert result.platform is Platform.TWITCH
    assert adapter.calls == ["health"]


@pytest.mark.asyncio
async def test_rejects_a_usable_connection_when_its_platform_has_no_adapter() -> None:
    current = connection()

    with pytest.raises(PlatformHealthUnavailableError, match="adapter"):
        await GetPlatformDashboardSummary(Authorizer(), Connections(current), {}).execute(
            actor_id=uuid4(),
            organization_id=current.organization_id,
            connection_id=current.id,
            correlation_id=uuid4(),
        )
