from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.change_email_password import PasswordChangeRejectedError
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, _: str) -> BrowserSessionPrincipal | None:
        return self.principal


class PasswordChangeUseCase:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.failure is not None:
            raise self.failure


def principal(actor_id: UUID, session_id: UUID) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=actor_id,
        session_id=session_id,
        assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


def client_with_session(
    *, actor_id: UUID | None = None, session_id: UUID | None = None, password_change=None
) -> TestClient:
    app = create_app(
        session_resolver=SessionResolver(principal(actor_id or uuid4(), session_id or uuid4())),
        password_change_use_case=password_change,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")
    return client


def payload() -> dict[str, str]:
    return {
        "current_password": "current-password",
        "new_password": "new-secure-password",
    }


def test_password_change_requires_session_and_csrf() -> None:
    missing_csrf = TestClient(create_app()).put("/api/v1/auth/password", json=payload())
    missing_session = TestClient(create_app(password_change_use_case=PasswordChangeUseCase())).put(
        "/api/v1/auth/password",
        json=payload(),
        headers={"Cookie": f"{CSRF_COOKIE_NAME}=csrf-token", CSRF_HEADER_NAME: "csrf-token"},
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json() == {"detail": "CSRF validation failed"}
    assert missing_session.status_code == 403
    assert missing_session.json() == {"detail": "Access denied"}


def test_password_change_maps_browser_session_to_use_case_command() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    use_case = PasswordChangeUseCase()
    client = client_with_session(
        actor_id=actor_id, session_id=session_id, password_change=use_case
    )

    response = client.put(
        "/api/v1/auth/password",
        json=payload(),
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 204
    assert use_case.command.principal.user_id == actor_id
    assert use_case.command.principal.session_id == session_id
    assert use_case.command.current_password == "current-password"
    assert use_case.command.new_password == "new-secure-password"
    assert isinstance(use_case.command.correlation_id, UUID)


def test_password_change_reports_recent_authentication_requirement() -> None:
    client = client_with_session(
        password_change=PasswordChangeUseCase(
            RecentAuthenticationRequiredError("Recent authentication required.")
        )
    )

    response = client.put(
        "/api/v1/auth/password",
        json=payload(),
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Recent authentication is required"}


def test_password_change_hides_rejection_reason() -> None:
    client = client_with_session(
        password_change=PasswordChangeUseCase(PasswordChangeRejectedError("Wrong password."))
    )

    response = client.put(
        "/api/v1/auth/password",
        json=payload(),
        headers={CSRF_HEADER_NAME: "csrf-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Password change failed"}
