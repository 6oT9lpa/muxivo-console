from uuid import uuid4

import pytest
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.get_platform_server_stats import GetPlatformServerStats
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationDecision
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.server_stats import PlatformServerStats, ServerStatsSummary


def stats(platform: Platform = Platform.DISCORD) -> PlatformServerStats:
    return PlatformServerStats(
        platform=platform,
        summary=ServerStatsSummary(
            total_messages=1,
            active_users=1,
            active_channels=1,
            daily_active_users=1,
            weekly_active_users=1,
            monthly_active_users=1,
            messages_per_active_user=1.0,
            voice_users=0,
            total_voice_minutes=0,
            joins=0,
            leaves=0,
            joins_24h=0,
            joins_7d=0,
            joins_30d=0,
            leaves_24h=0,
            leaves_7d=0,
            leaves_30d=0,
            net_member_growth=0,
            current_member_count=1,
            moderation_events=0,
            membership_history_since=None,
            membership_history_complete=False,
            period_days=30,
        ),
        channels=(),
        hourly=(),
        daily=(),
    )


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.request = None

    async def authorize(self, request):
        self.request = request
        return AuthorizationDecision(self.allowed)


class Connections:
    def __init__(self, connection: PlatformConnection | None) -> None:
        self.connection = connection

    async def find_for_organization(self, **kwargs):
        return self.connection


class StatsReader:
    def __init__(self, result: PlatformServerStats) -> None:
        self.result = result
        self.arguments = None

    async def get_server_stats_for_connection(self, **kwargs):
        self.arguments = kwargs
        return self.result


def connection(status: ConnectionStatus = ConnectionStatus.ACTIVE) -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=status,
    )


@pytest.mark.asyncio
async def test_server_stats_are_routed_through_selected_connection() -> None:
    selected = connection()
    reader = StatsReader(stats())
    use_case = GetPlatformServerStats(Authorizer(), Connections(selected), reader)
    actor_id, correlation_id = uuid4(), uuid4()

    result = await use_case.execute(
        actor_id=actor_id,
        organization_id=selected.organization_id,
        connection_id=selected.id,
        period_days=30,
        correlation_id=correlation_id,
    )

    assert result.summary.total_messages == 1
    assert reader.arguments["platform"] is Platform.DISCORD
    assert reader.arguments["external_resource_id"] == selected.external_resource_id
    assert reader.arguments["period_days"] == 30


@pytest.mark.asyncio
async def test_server_stats_denies_before_reading_connection() -> None:
    selected = connection()
    use_case = GetPlatformServerStats(
        Authorizer(False), Connections(selected), StatsReader(stats())
    )

    with pytest.raises(AccessDeniedError):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=selected.organization_id,
            connection_id=selected.id,
            period_days=30,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_server_stats_requires_usable_connection() -> None:
    selected = connection(ConnectionStatus.DISCONNECTED)
    use_case = GetPlatformServerStats(
        Authorizer(), Connections(selected), StatsReader(stats())
    )

    with pytest.raises(PlatformHealthUnavailableError):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=selected.organization_id,
            connection_id=selected.id,
            period_days=30,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_server_stats_validates_period_before_authorization() -> None:
    selected = connection()
    authorizer = Authorizer()
    use_case = GetPlatformServerStats(authorizer, Connections(selected), StatsReader(stats()))

    with pytest.raises(ValueError, match="between 1 and 365"):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=selected.organization_id,
            connection_id=selected.id,
            period_days=0,
            correlation_id=uuid4(),
        )

    assert authorizer.request is None
