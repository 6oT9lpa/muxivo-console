from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.begin_identity_link import StartedIdentityLink
from muxivo_console.application.complete_identity_link import IdentityLinkCompletionRejectedError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class SessionResolver:
    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)


class StartUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command) -> StartedIdentityLink:
        self.command = command
        return StartedIdentityLink("opaque-state", "pkce-challenge", 600)


class CompleteUseCase:
    def __init__(self, reject: bool = False) -> None:
        self.reject = reject
        self.command = None

    async def execute(self, command) -> None:
        self.command = command
        if self.reject:
            raise IdentityLinkCompletionRejectedError("Rejected")


def headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def test_starts_discord_identity_link_only_for_session_with_csrf() -> None:
    start = StartUseCase()
    client = TestClient(
        create_app(
            session_resolver=SessionResolver(),
            discord_identity_link_start=start,
            discord_authorization_url=lambda **params: (
                f"https://discord.test/oauth?state={params['state']}"
            ),
        )
    )

    response = client.post("/api/v1/identity-links/discord/authorizations", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "authorization_url": "https://discord.test/oauth?state=opaque-state",
        "expires_in_seconds": 600,
    }
    assert start.command.provider.value == "discord"
    assert isinstance(start.command.actor_id, UUID)


def test_callback_completes_state_flow_without_requiring_browser_session() -> None:
    complete = CompleteUseCase()
    client = TestClient(create_app(discord_identity_link_complete=complete))

    response = client.get(
        "/api/v1/identity-links/discord/callback?code=oauth-code&state=opaque-state"
    )

    assert response.status_code == 200
    assert response.json() == {"linked": True}
    assert complete.command.authorization_code == "oauth-code"
    assert complete.command.state == "opaque-state"


def test_canonical_auth_callback_can_complete_identity_link_state_flow() -> None:
    complete = CompleteUseCase()
    client = TestClient(create_app(discord_identity_link_complete=complete))

    response = client.get("/api/v1/auth/discord/callback?code=oauth-code&state=opaque-state")

    assert response.status_code == 200
    assert response.json() == {"linked": True}
    assert complete.command.authorization_code == "oauth-code"
    assert complete.command.state == "opaque-state"


def test_callback_hides_state_or_provider_failure_reason() -> None:
    client = TestClient(create_app(discord_identity_link_complete=CompleteUseCase(reject=True)))

    response = client.get("/api/v1/identity-links/discord/callback?code=code&state=state")

    assert response.status_code == 400
    assert response.json() == {"detail": "Discord identity linking failed"}


def test_starts_twitch_identity_link_with_matching_provider_mapping() -> None:
    start = StartUseCase()
    client = TestClient(
        create_app(
            session_resolver=SessionResolver(),
            twitch_identity_link_start=start,
            twitch_authorization_url=lambda **params: (
                f"https://twitch.test/oauth?state={params['state']}"
            ),
        )
    )

    response = client.post("/api/v1/identity-links/twitch/authorizations", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "authorization_url": "https://twitch.test/oauth?state=opaque-state",
        "expires_in_seconds": 600,
    }
    assert start.command.provider.value == "twitch"
    assert isinstance(start.command.actor_id, UUID)


def test_twitch_callback_completes_twitch_identity_link_state_flow() -> None:
    complete = CompleteUseCase()
    client = TestClient(create_app(twitch_identity_link_complete=complete))

    response = client.get("/api/v1/auth/twitch/callback?code=oauth-code&state=opaque-state")

    assert response.status_code == 200
    assert response.json() == {"linked": True}
    assert complete.command.provider.value == "twitch"
    assert complete.command.authorization_code == "oauth-code"
    assert complete.command.state == "opaque-state"


def test_twitch_callback_hides_state_or_provider_failure_reason() -> None:
    client = TestClient(create_app(twitch_identity_link_complete=CompleteUseCase(reject=True)))

    response = client.get("/api/v1/identity-links/twitch/callback?code=code&state=state")

    assert response.status_code == 400
    assert response.json() == {"detail": "Twitch identity linking failed"}
