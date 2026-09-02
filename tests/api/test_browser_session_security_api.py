from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_browser_sessions import (
    BrowserSessionListRejectedError,
    BrowserSessionSecurityView,
)
from muxivo_console.application.reauthenticate_browser_session import (
    BrowserSessionReauthenticationRejectedError,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.application.revoke_all_browser_sessions import (
    BrowserSessionBulkRevocationRejectedError,
)
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class SessionResolver:
    def __init__(
        self,
        actor_id: UUID,
        session_id: UUID,
        *,
        assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at: datetime | None = datetime(2026, 8, 9, tzinfo=UTC),
    ) -> None:
        self.actor_id = actor_id
        self.session_id = session_id
        self.assurance_level = assurance_level
        self.authenticated_at = authenticated_at

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id,
            self.session_id,
            self.assurance_level,
            self.authenticated_at,
        )


class SessionListUseCase:
    def __init__(self, sessions: tuple[BrowserSessionSecurityView, ...], rejects: bool = False):
        self.sessions = sessions
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise BrowserSessionListRejectedError("Access denied.")
        return self.sessions


class SessionBulkRevoker:
    def __init__(
        self,
        revoked_count: int = 2,
        rejects: bool = False,
        recent_auth_required: bool = False,
    ) -> None:
        self.revoked_count = revoked_count
        self.rejects = rejects
        self.recent_auth_required = recent_auth_required
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.recent_auth_required:
            raise RecentAuthenticationRequiredError("Recent authentication required.")
        if self.rejects:
            raise BrowserSessionBulkRevocationRejectedError("Access denied.")
        return self.revoked_count


class SessionReauthenticationUseCase:
    def __init__(self, rejects: bool = False) -> None:
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise BrowserSessionReauthenticationRejectedError("Reauthentication failed.")


def csrf_headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-browser-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def stored_session(actor_id: UUID, session_id: UUID) -> AuthSession:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    return AuthSession(
        id=session_id,
        user_id=actor_id,
        token_hash="a" * 64,
        expires_at=now + timedelta(days=14),
        assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at=now,
        last_seen_at=now + timedelta(minutes=10),
        ip_hash="b" * 64,
        user_agent_hash="c" * 64,
    )


def test_lists_current_user_browser_sessions_with_safe_fingerprints() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    listing = SessionListUseCase(
        (BrowserSessionSecurityView(stored_session(actor_id, session_id), True),)
    )
    app = create_app(
        session_resolver=SessionResolver(actor_id, session_id),
        session_list_use_case=listing,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")

    response = client.get("/api/v1/auth/sessions")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": str(session_id),
            "is_current": True,
            "assurance_level": "recent_authentication",
            "authenticated_at": "2026-08-09T00:00:00Z",
            "last_seen_at": "2026-08-09T00:10:00Z",
            "expires_at": "2026-08-23T00:00:00Z",
            "device_label": "Browser:cccccccccccc",
            "ip_fingerprint": "ip:bbbbbbbbbbbb",
            "user_agent_fingerprint": "ua:cccccccccccc",
        }
    ]
    assert listing.command.actor_id == actor_id
    assert listing.command.current_session_id == session_id


def test_revoke_all_browser_sessions_clears_browser_cookies() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    revoker = SessionBulkRevoker(3)
    app = create_app(
        session_resolver=SessionResolver(actor_id, session_id),
        session_bulk_revoker=revoker,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.delete("/api/v1/auth/sessions", headers={CSRF_HEADER_NAME: "csrf-token"})

    assert response.status_code == 200
    assert response.json() == {"revoked_count": 3}
    assert revoker.command.principal.user_id == actor_id
    assert revoker.command.principal.session_id == session_id
    assert f"{SESSION_COOKIE_NAME}=" in response.headers["set-cookie"]
    assert f"{CSRF_COOKIE_NAME}=" in response.headers["set-cookie"]


def test_revoke_all_browser_sessions_requires_recent_authentication() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    revoker = SessionBulkRevoker(3, recent_auth_required=True)
    app = create_app(
        session_resolver=SessionResolver(
            actor_id,
            session_id,
            assurance_level=SessionAssuranceLevel.PASSWORD,
            authenticated_at=datetime(2026, 8, 9, tzinfo=UTC),
        ),
        session_bulk_revoker=revoker,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.delete("/api/v1/auth/sessions", headers={CSRF_HEADER_NAME: "csrf-token"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Recent authentication required"}
    assert revoker.command is not None


def test_session_listing_hides_rejection_reason() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    app = create_app(
        session_resolver=SessionResolver(actor_id, session_id),
        session_list_use_case=SessionListUseCase((), rejects=True),
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")

    response = client.get("/api/v1/auth/sessions")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_reauthenticate_browser_session_requires_current_password_and_csrf() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    use_case = SessionReauthenticationUseCase()
    app = create_app(
        session_resolver=SessionResolver(actor_id, session_id),
        session_reauthentication_use_case=use_case,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.post(
        "/api/v1/auth/session/reauthentications",
        headers={CSRF_HEADER_NAME: "csrf-token"},
        json={"current_password": "correct-password"},
    )

    assert response.status_code == 204
    assert use_case.command.principal.user_id == actor_id
    assert use_case.command.principal.session_id == session_id
    assert use_case.command.current_password == "correct-password"


def test_reauthenticate_browser_session_hides_rejection_reason() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    app = create_app(
        session_resolver=SessionResolver(actor_id, session_id),
        session_reauthentication_use_case=SessionReauthenticationUseCase(rejects=True),
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")
    client.cookies.set(CSRF_COOKIE_NAME, "csrf-token")

    response = client.post(
        "/api/v1/auth/session/reauthentications",
        headers={CSRF_HEADER_NAME: "csrf-token"},
        json={"current_password": "wrong-password"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Session reauthentication failed"}
