from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.server_statistics import PlatformServerStatistics
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class StatisticsUseCase:
    def __init__(self, result: PlatformServerStatistics | Exception) -> None:
        self.result = result

    async def execute(self, **_: object) -> PlatformServerStatistics:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def client_for(actor_id: UUID, result: PlatformServerStatistics | Exception) -> TestClient:
    client = TestClient(
        create_app(
            platform_server_statistics_use_case=StatisticsUseCase(result),
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_aggregate_platform_server_statistics() -> None:
    organization_id, connection_id = uuid4(), uuid4()
    response = client_for(
        uuid4(),
        PlatformServerStatistics(
            Platform.DISCORD,
            7,
            150,
            42,
            8,
            200,
            360,
            5,
            2,
            3,
        ),
    ).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/"
        f"{connection_id}/server-statistics"
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "connection_id": str(connection_id),
        "platform": "discord",
        "period_days": 7,
        "total_messages": 150,
        "active_users": 42,
        "active_channels": 8,
        "current_member_count": 200,
        "total_voice_minutes": 360,
        "joins": 5,
        "leaves": 2,
        "net_member_growth": 3,
        "moderation_events": 3,
    }


def test_hides_unavailable_server_statistics_connection_details() -> None:
    response = client_for(
        uuid4(),
        PlatformHealthUnavailableError("not available"),
    ).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/"
        f"{uuid4()}/server-statistics"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform server statistics are unavailable"}
