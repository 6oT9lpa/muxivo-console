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


def twitch_authorization_url(*, state: str, code_challenge: str) -> str:
    assert (state, code_challenge) == ("state", "challenge")
    return "https://twitch.example/authorize"


def google_authorization_url(*, state: str, code_challenge: str) -> str:
    assert (state, code_challenge) == ("state", "challenge")
    return "https://google.example/authorize"


def yandex_authorization_url(*, state: str, code_challenge: str) -> str:
    assert (state, code_challenge) == ("state", "challenge")
    return "https://yandex.example/authorize"


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
        "/api/v1/auth/discord/callback?code=oauth-code&state=oauth-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "__Host-muxivo_session=opaque-session" in response.headers["set-cookie"]
    assert "__Host-muxivo_csrf=csrf-token" in response.headers["set-cookie"]
    assert complete.arguments is not None
    assert complete.arguments["authorization_code"] == "oauth-code"
    assert complete.arguments["client_ip"]
    assert complete.arguments["user_agent"] == "testclient"


def test_starts_twitch_oauth_login_without_a_browser_session() -> None:
    start = LoginStart()
    client = TestClient(
        create_app(twitch_login_start=start, twitch_authorization_url=twitch_authorization_url)
    )

    response = client.post("/api/v1/auth/twitch/authorizations")

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://twitch.example/authorize"
    assert start.arguments is not None
    assert start.arguments["provider"].value == "twitch"


def test_twitch_oauth_callback_sets_first_party_cookies_and_redirects_to_console() -> None:
    complete = LoginComplete()
    client = TestClient(create_app(twitch_login_complete=complete))

    response = client.get(
        "/api/v1/auth/twitch/callback?code=oauth-code&state=oauth-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "__Host-muxivo_session=opaque-session" in response.headers["set-cookie"]
    assert "__Host-muxivo_csrf=csrf-token" in response.headers["set-cookie"]
    assert complete.arguments is not None
    assert complete.arguments["provider"].value == "twitch"


def test_starts_google_oauth_login_without_a_browser_session() -> None:
    start = LoginStart()
    client = TestClient(
        create_app(google_login_start=start, google_authorization_url=google_authorization_url)
    )

    response = client.post("/api/v1/auth/google/authorizations")

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://google.example/authorize"
    assert start.arguments is not None
    assert start.arguments["provider"].value == "google"


def test_starts_yandex_oauth_login_without_a_browser_session() -> None:
    start = LoginStart()
    client = TestClient(
        create_app(yandex_login_start=start, yandex_authorization_url=yandex_authorization_url)
    )

    response = client.post("/api/v1/auth/yandex/authorizations")

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://yandex.example/authorize"
    assert start.arguments is not None
    assert start.arguments["provider"].value == "yandex"


def test_google_oauth_callback_sets_first_party_cookies_and_redirects_to_console() -> None:
    complete = LoginComplete()
    client = TestClient(create_app(google_login_complete=complete))

    response = client.get(
        "/api/v1/auth/google/callback?code=oauth-code&state=oauth-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "__Host-muxivo_session=opaque-session" in response.headers["set-cookie"]
    assert "__Host-muxivo_csrf=csrf-token" in response.headers["set-cookie"]
    assert complete.arguments is not None
    assert complete.arguments["provider"].value == "google"


def test_provider_catalog_lists_only_configured_oauth_login_providers() -> None:
    client = TestClient(
        create_app(
            discord_login_start=LoginStart(),
            discord_authorization_url=authorization_url,
            twitch_login_start=LoginStart(),
            twitch_authorization_url=twitch_authorization_url,
        )
    )

    response = client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    assert response.json() == {"providers": ["discord", "twitch"]}


def test_provider_catalog_includes_google_and_yandex_when_configured() -> None:
    client = TestClient(
        create_app(
            google_login_start=LoginStart(),
            google_authorization_url=google_authorization_url,
            yandex_login_start=LoginStart(),
            yandex_authorization_url=yandex_authorization_url,
        )
    )

    response = client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    assert response.json() == {"providers": ["google", "yandex"]}
