from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal
        self.raw_token: str | None = None

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        self.raw_token = raw_token
        return self.principal


def test_current_session_restores_non_secret_browser_principal() -> None:
    principal = BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )
    resolver = SessionResolver(principal)
    client = TestClient(create_app(session_resolver=resolver), base_url="https://testserver")

    response = client.get(
        "/api/v1/auth/sessions/current",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(principal.user_id),
        "session_id": str(principal.session_id),
        "assurance_level": "password",
    }
    assert resolver.raw_token == "opaque-session-token"


def test_current_session_rejects_anonymous_browser() -> None:
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.get("/api/v1/auth/sessions/current")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_current_session_fails_closed_when_resolver_rejects_cookie() -> None:
    resolver = SessionResolver(None)
    client = TestClient(create_app(session_resolver=resolver), base_url="https://testserver")

    response = client.get(
        "/api/v1/auth/sessions/current",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=expired-or-revoked"},
    )

    assert response.status_code == 401
    assert resolver.raw_token == "expired-or-revoked"
