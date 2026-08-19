from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID, session_id: UUID) -> None:
        self.actor_id = actor_id
        self.session_id = session_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id, self.session_id, SessionAssuranceLevel.PASSWORD
        )


class SessionRevoker:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> None:
        self.arguments = arguments


def test_revokes_only_current_browser_session_and_clears_both_cookies() -> None:
    actor_id, session_id = uuid4(), uuid4()
    revoker = SessionRevoker()
    client = TestClient(
        create_app(
            session_resolver=SessionResolver(actor_id, session_id), session_revoker=revoker
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    client.cookies.set("__Host-muxivo_csrf", "csrf-token")

    response = client.delete(
        "/api/v1/auth/session", headers={"X-CSRF-Token": "csrf-token"}
    )

    assert response.status_code == 204
    assert revoker.arguments is not None
    assert revoker.arguments["user_id"] == actor_id
    assert revoker.arguments["session_id"] == session_id
    assert "__Host-muxivo_session=" in response.headers["set-cookie"]
    assert "__Host-muxivo_csrf=" in response.headers["set-cookie"]
