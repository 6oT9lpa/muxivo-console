from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.bot_settings import PlatformBotSettings
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class BotSettingsUseCase:
    def __init__(self, result: PlatformBotSettings | Exception) -> None:
        self.result = result
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments) -> PlatformBotSettings:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def authenticated_client(actor_id: UUID, use_case: BotSettingsUseCase) -> TestClient:
    client = TestClient(
        create_app(
            platform_bot_settings_use_case=use_case,
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_a_non_secret_bot_settings_projection_for_a_connection() -> None:
    actor_id, organization_id, connection_id = uuid4(), uuid4(), uuid4()
    use_case = BotSettingsUseCase(
        PlatformBotSettings(
            Platform.DISCORD,
            "plus",
            True,
            60,
            (("message_log_retention_days", 30), ("punishment_retention_days", 90)),
        )
    )

    response = authenticated_client(actor_id, use_case).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/bot-settings"
    )

    assert response.status_code == 200
    assert response.json()["subscription_tier"] == "plus"
    assert response.json()["retention_days"] == {
        "message_log_retention_days": 30,
        "punishment_retention_days": 90,
    }
    assert use_case.arguments is not None
    assert use_case.arguments["actor_id"] == actor_id
    assert "external_resource_id" not in use_case.arguments


def test_hides_unavailable_connection_details() -> None:
    response = authenticated_client(
        uuid4(), BotSettingsUseCase(PlatformHealthUnavailableError("not available"))
    ).get(f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/bot-settings")

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform bot settings are unavailable"}
