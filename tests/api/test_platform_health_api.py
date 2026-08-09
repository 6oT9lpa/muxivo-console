from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)


class HealthUseCase:
    def __init__(self, result: PlatformHealth | Exception) -> None:
        self.result = result
        self.arguments = None

    async def execute(self, **arguments) -> PlatformHealth:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def authenticated_client(use_case: HealthUseCase) -> TestClient:
    client = TestClient(
        create_app(platform_health_use_case=use_case, session_resolver=SessionResolver())
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_platform_neutral_health_contract() -> None:
    organization_id = uuid4()
    use_case = HealthUseCase(
        PlatformHealth(
            platform=Platform.DISCORD,
            signals=(
                HealthSignal(
                    key="discord.bot-latency",
                    display_name="Bot latency",
                    value="12 ms",
                    status=HealthStatus.OPERATIONAL,
                    latency_ms=12,
                ),
            ),
        )
    )

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{organization_id}/platforms/discord/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "platform": "discord",
        "signals": [
            {
                "key": "discord.bot-latency",
                "display_name": "Bot latency",
                "value": "12 ms",
                "status": "operational",
                "latency_ms": 12,
            }
        ],
    }
    assert use_case.arguments["organization_id"] == organization_id
    assert use_case.arguments["platform"] is Platform.DISCORD


def test_returns_not_found_when_organization_has_no_usable_platform_connection() -> None:
    use_case = HealthUseCase(PlatformHealthUnavailableError("not connected"))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/platforms/discord/health"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform health is unavailable"}


def test_requires_a_browser_session() -> None:
    client = TestClient(create_app())

    response = client.get(f"/api/v1/organizations/{uuid4()}/platforms/discord/health")

    assert response.status_code == 403
