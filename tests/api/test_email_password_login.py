from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.authenticate_email_password import AuthenticationRejectedError
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, create_app


class AuthenticationUseCase:
    def __init__(self, should_reject: bool = False) -> None:
        self.should_reject = should_reject
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.should_reject:
            raise AuthenticationRejectedError("Authentication could not be completed.")
        return IssuedBrowserSession(
            id=uuid4(),
            raw_token="opaque-browser-session",
            raw_csrf_token="opaque-csrf-token",
            expires_at=datetime.now(UTC) + timedelta(days=14),
            assurance_level=SessionAssuranceLevel.PASSWORD,
        )


def payload() -> dict[str, str]:
    return {"email": "creator@example.com", "password": "a-long-enough-password"}


def test_login_sets_host_only_session_and_csrf_cookies() -> None:
    authentication = AuthenticationUseCase()
    client = TestClient(create_app(authentication_use_case=authentication))

    response = client.post("/api/v1/auth/email-password/sessions", json=payload())

    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith(SESSION_COOKIE_NAME))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith(CSRF_COOKIE_NAME))
    assert response.status_code == 204
    assert f"{SESSION_COOKIE_NAME}=opaque-browser-session" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "Path=/" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Secure" in session_cookie
    assert "Domain=" not in session_cookie
    assert f"{CSRF_COOKIE_NAME}=opaque-csrf-token" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Path=/" in csrf_cookie
    assert "SameSite=lax" in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "Domain=" not in csrf_cookie
    assert authentication.command.email == "creator@example.com"
    assert authentication.command.password == "a-long-enough-password"


def test_login_rejection_has_single_generic_public_failure() -> None:
    client = TestClient(create_app(authentication_use_case=AuthenticationUseCase(True)))

    response = client.post("/api/v1/auth/email-password/sessions", json=payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}
    assert "set-cookie" not in response.headers


def test_login_is_unavailable_without_explicit_secure_runtime_wiring() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/auth/email-password/sessions", json=payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is unavailable"}
