from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_control_modules import ListControlModules
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.infrastructure.development import StaticModuleCatalog
from muxivo_console.presentation.api import create_app


class AllowAuthorizer:
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.allow()


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal
        self.received_token: str | None = None

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        self.received_token = raw_token
        return self.principal


def test_requires_an_authenticated_principal() -> None:
    client = TestClient(create_app())
    response = client.get(f"/api/v1/organizations/{uuid4()}/control-modules")
    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_returns_versioned_platform_neutral_contract_for_authorized_actor() -> None:
    actor_id = uuid4()
    session_resolver = SessionResolver(
        BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
    )
    app = create_app(
        control_modules_use_case=ListControlModules(AllowAuthorizer(), StaticModuleCatalog()),
        session_resolver=session_resolver,
    )

    client = TestClient(app)
    client.cookies.set("__Host-muxivo_session", "opaque-browser-token")
    organization_id = uuid4()
    response = client.get(f"/api/v1/organizations/{organization_id}/control-modules")
    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "items": [
            {
                "key": "discord.dashboard",
                "display_name": "Discord dashboard",
                "platform": "discord",
                "capability": "view",
                "status": "available",
            }
        ],
    }
    assert session_resolver.received_token == "opaque-browser-token"


def test_invalid_cookie_never_becomes_a_principal() -> None:
    app = create_app(
        control_modules_use_case=ListControlModules(AllowAuthorizer(), StaticModuleCatalog()),
        session_resolver=SessionResolver(None),
    )
    client = TestClient(app)
    client.cookies.set("__Host-muxivo_session", "rejected-token")

    response = client.get(f"/api/v1/organizations/{uuid4()}/control-modules")

    assert response.status_code == 403
