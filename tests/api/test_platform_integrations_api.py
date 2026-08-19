from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.integrations import IntegrationSourceCount, PlatformIntegrations
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class IntegrationsUseCase:
    def __init__(self, result: PlatformIntegrations | Exception) -> None:
        self.result = result

    async def execute(self, **_: object) -> PlatformIntegrations:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def client_for(actor_id: UUID, result: PlatformIntegrations | Exception) -> TestClient:
    client = TestClient(
        create_app(
            platform_integrations_use_case=IntegrationsUseCase(result),
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_secret_free_platform_integrations() -> None:
    organization_id, connection_id = uuid4(), uuid4()
    response = client_for(
        uuid4(),
        PlatformIntegrations(
            Platform.DISCORD,
            "configured",
            "configured",
            60,
            (IntegrationSourceCount("twitch", 2, 1),),
            "configured",
            "configured",
        ),
    ).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/integrations"
    )

    assert response.status_code == 200
    assert response.json()["creator_sources"] == [
        {"platform": "twitch", "total": 2, "active": 1}
    ]
    assert "endpoint" not in response.json()


def test_hides_unavailable_integrations_connection_details() -> None:
    response = client_for(
        uuid4(), PlatformHealthUnavailableError("not available")
    ).get(f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/integrations")

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform integrations are unavailable"}
