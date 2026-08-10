from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, create_app
from muxivo_console.presentation.browser_sessions import create_browser_session_router


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class RevocationUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command) -> bool:
        self.command = command
        return True


def app_with_session(principal: BrowserSessionPrincipal | None):
    revocation = RevocationUseCase()
    app = create_app(session_resolver=SessionResolver(principal))
    app.include_router(create_browser_session_router(revocation))
    return app, revocation


def request_headers() -> dict[str, str]:
    return {
        "Cookie": (
            f"{SESSION_COOKIE_NAME}=opaque-session; "
            f"{CSRF_COOKIE_NAME}=opaque-csrf"
        ),
        "X-CSRF-Token": "opaque-csrf",
    }


def test_logout_revokes_bound_session_and_expires_both_browser_cookies() -> None:
    principal = BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )
    app, revocation = app_with_session(principal)
    client = TestClient(app, base_url="https://testserver")

    response = client.delete("/api/v1/auth/sessions/current", headers=request_headers())

    assert response.status_code == 204
    assert revocation.command.actor_id == principal.user_id
    assert revocation.command.session_id == principal.session_id
    cookies = response.headers.get_list("set-cookie")
    assert any(
        cookie.startswith(f"{SESSION_COOKIE_NAME}=") and "Max-Age=0" in cookie
        for cookie in cookies
    )
    assert any(
        cookie.startswith(f"{CSRF_COOKIE_NAME}=") and "Max-Age=0" in cookie
        for cookie in cookies
    )


def test_logout_rejects_anonymous_browser() -> None:
    app, revocation = app_with_session(None)
    client = TestClient(app, base_url="https://testserver")

    response = client.delete("/api/v1/auth/sessions/current", headers=request_headers())

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert revocation.command is None


def test_logout_requires_csrf_before_revocation() -> None:
    principal = BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )
    app, revocation = app_with_session(principal)
    client = TestClient(app, base_url="https://testserver")

    response = client.delete(
        "/api/v1/auth/sessions/current",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == 403
    assert revocation.command is None
