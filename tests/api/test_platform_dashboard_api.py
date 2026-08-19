from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class DashboardUseCase:
    def __init__(self, result: PlatformDashboardSummary | Exception) -> None:
        self.result = result
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments) -> PlatformDashboardSummary:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def authenticated_client(actor_id: UUID, use_case: DashboardUseCase) -> TestClient:
    client = TestClient(
        create_app(
            platform_dashboard_use_case=use_case,
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_dashboard_from_a_console_connection_identifier() -> None:
    actor_id, organization_id, connection_id = uuid4(), uuid4(), uuid4()
    use_case = DashboardUseCase(
        PlatformDashboardSummary(
            platform=Platform.DISCORD,
            messages_today=42,
            ai_flagged_today=3,
            creator_sources=2,
            bot_latency_ms=12,
        )
    )

    response = authenticated_client(actor_id, use_case).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/dashboard"
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "connection_id": str(connection_id),
        "platform": "discord",
        "messages_today": 42,
        "ai_flagged_today": 3,
        "creator_sources": 2,
        "bot_latency_ms": 12,
    }
    assert use_case.arguments is not None
    assert use_case.arguments["actor_id"] == actor_id
    assert use_case.arguments["connection_id"] == connection_id
    assert "external_resource_id" not in use_case.arguments


def test_hides_missing_or_unusable_connection_details() -> None:
    use_case = DashboardUseCase(PlatformHealthUnavailableError("not available"))

    response = authenticated_client(uuid4(), use_case).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/dashboard"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform dashboard is unavailable"}


def test_requires_a_browser_session() -> None:
    response = TestClient(create_app()).get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/dashboard"
    )

    assert response.status_code == 403
