from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.server_stats import (
    PlatformServerStats,
    ServerChannelStats,
    ServerDailyStats,
    ServerHourlyStats,
    ServerStatsSummary,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app
from muxivo_console.presentation.server_stats import create_server_stats_router


class SessionResolver:
    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)


class StatsUseCase:
    def __init__(self, result: PlatformServerStats | Exception) -> None:
        self.result = result
        self.arguments = None

    async def execute(self, **arguments) -> PlatformServerStats:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def sample_stats() -> PlatformServerStats:
    return PlatformServerStats(
        Platform.DISCORD,
        ServerStatsSummary(
            total_messages=120,
            active_users=20,
            active_channels=4,
            daily_active_users=8,
            weekly_active_users=15,
            monthly_active_users=20,
            messages_per_active_user=6.0,
            voice_users=5,
            total_voice_minutes=300,
            joins=12,
            leaves=2,
            joins_24h=1,
            joins_7d=4,
            joins_30d=12,
            leaves_24h=0,
            leaves_7d=1,
            leaves_30d=2,
            net_member_growth=10,
            current_member_count=450,
            moderation_events=7,
            membership_history_since=None,
            membership_history_complete=False,
            period_days=30,
        ),
        (ServerChannelStats("123", "general", 80),),
        (ServerHourlyStats(12, 11),),
        (ServerDailyStats("2026-08-10", 22),),
    )


def authenticated_client(use_case: StatsUseCase) -> TestClient:
    app = create_app(session_resolver=SessionResolver())
    app.include_router(create_server_stats_router(use_case))
    client = TestClient(app)
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_platform_neutral_server_stats_contract() -> None:
    organization_id, connection_id = uuid4(), uuid4()
    use_case = StatsUseCase(sample_stats())

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/server-stats?period=30"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization_id"] == str(organization_id)
    assert payload["connection_id"] == str(connection_id)
    assert payload["platform"] == "discord"
    assert payload["summary"]["total_messages"] == 120
    assert payload["summary"]["voice_users"] == 5
    assert payload["channels"] == [
        {"channel_id": "123", "channel_name": "general", "messages": 80}
    ]
    assert use_case.arguments["period_days"] == 30


def test_maps_missing_connection_to_not_found() -> None:
    use_case = StatsUseCase(PlatformHealthUnavailableError("missing"))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/server-stats"
    )

    assert response.status_code == 404


def test_maps_platform_failure_to_service_unavailable() -> None:
    use_case = StatsUseCase(PlatformControlUnavailableError("upstream detail"))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/server-stats"
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Platform control service is unavailable"}


def test_rejects_period_outside_activity_contract() -> None:
    use_case = StatsUseCase(sample_stats())

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/server-stats?period=366"
    )

    assert response.status_code == 422
    assert use_case.arguments is None
