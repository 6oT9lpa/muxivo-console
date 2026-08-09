from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.authenticate_email_password import AuthenticationRejectedError
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app


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
            expires_at=datetime.now(UTC) + timedelta(days=14),
            assurance_level=SessionAssuranceLevel.PASSWORD,
        )


def payload() -> dict[str, str]:
    return {"email": "creator@example.com", "password": "a-long-enough-password"}


def test_login_sets_host_only_secure_http_only_lax_session_cookie() -> None:
    authentication = AuthenticationUseCase()
    client = TestClient(create_app(authentication_use_case=authentication))

    response = client.post("/api/v1/auth/email-password/sessions", json=payload())

    cookie = response.headers["set-cookie"]
    assert response.status_code == 204
    assert f"{SESSION_COOKIE_NAME}=opaque-browser-session" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie
    assert "Domain=" not in cookie
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
