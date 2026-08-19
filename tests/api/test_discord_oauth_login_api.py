from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.begin_oauth_login import StartedOAuthLogin
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class LoginStart:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> StartedOAuthLogin:
        self.arguments = arguments
        return StartedOAuthLogin("state", "challenge", 600)


class LoginComplete:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> IssuedBrowserSession:
        self.arguments = arguments
        return IssuedBrowserSession(
            id=uuid4(),
            raw_token="opaque-session",
            raw_csrf_token="csrf-token",
            expires_at=datetime(2026, 8, 20, tzinfo=UTC) + timedelta(days=14),
            assurance_level=SessionAssuranceLevel.PASSWORD,
        )


def authorization_url(*, state: str, code_challenge: str) -> str:
    assert (state, code_challenge) == ("state", "challenge")
    return "https://discord.example/authorize"


def test_starts_discord_oauth_login_without_a_browser_session() -> None:
    start = LoginStart()
    client = TestClient(
        create_app(discord_login_start=start, discord_authorization_url=authorization_url)
    )

    response = client.post("/api/v1/auth/discord/authorizations")

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://discord.example/authorize"
    assert start.arguments is not None
    assert start.arguments["provider"].value == "discord"


def test_discord_oauth_callback_sets_first_party_cookies_and_redirects_to_console() -> None:
    complete = LoginComplete()
    client = TestClient(create_app(discord_login_complete=complete))

    response = client.get(
        "/api/v1/identity-links/discord/callback?code=oauth-code&state=oauth-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "__Host-muxivo_session=opaque-session" in response.headers["set-cookie"]
    assert "__Host-muxivo_csrf=csrf-token" in response.headers["set-cookie"]
    assert complete.arguments is not None
    assert complete.arguments["authorization_code"] == "oauth-code"
