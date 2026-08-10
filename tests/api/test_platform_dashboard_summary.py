from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app
from muxivo_console.presentation.dashboard import create_dashboard_router


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class DashboardQuery:
    def __init__(self, result: PlatformDashboardSummary | Exception) -> None:
        self.result = result
        self.arguments = None

    async def execute(self, **kwargs) -> PlatformDashboardSummary:
        self.arguments = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def principal() -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )


def dashboard() -> PlatformDashboardSummary:
    return PlatformDashboardSummary(
        platform=Platform.DISCORD,
        messages_today=800,
        ai_flagged_today=12,
        creator_sources=3,
        bot_latency_ms=31,
    )


def client_for(query: DashboardQuery, actor: BrowserSessionPrincipal | None) -> TestClient:
    app = create_app(session_resolver=SessionResolver(actor))
    app.include_router(create_dashboard_router(query))
    return TestClient(app, base_url="https://testserver")


def test_dashboard_contract_binds_response_to_organization_and_connection() -> None:
    actor = principal()
    organization_id = uuid4()
    connection_id = uuid4()
    query = DashboardQuery(dashboard())
    client = client_for(query, actor)

    response = client.get(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/dashboard-summary",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "connection_id": str(connection_id),
        "platform": "discord",
        "messages_today": 800,
        "ai_flagged_today": 12,
        "creator_sources": 3,
        "bot_latency_ms": 31,
    }
    assert query.arguments["actor_id"] == actor.user_id
    assert query.arguments["organization_id"] == organization_id
    assert query.arguments["connection_id"] == connection_id


def test_dashboard_contract_denies_anonymous_browser() -> None:
    query = DashboardQuery(dashboard())
    client = client_for(query, None)

    response = client.get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/dashboard-summary"
    )

    assert response.status_code == 403
    assert query.arguments is None


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AccessDeniedError("denied"), 403),
        (PlatformHealthUnavailableError("not ready"), 404),
        (PlatformControlUnavailableError("down"), 503),
    ],
)
def test_dashboard_contract_maps_control_boundary_errors(error, expected_status) -> None:
    query = DashboardQuery(error)
    client = client_for(query, principal())

    response = client.get(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/dashboard-summary",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == expected_status
