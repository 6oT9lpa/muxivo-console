from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_control_modules import ListControlModules
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.infrastructure.development import StaticModuleCatalog
from muxivo_console.presentation.api import create_app


class AllowAuthorizer:
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.allow()


def test_requires_an_authenticated_principal() -> None:
    client = TestClient(create_app())
    response = client.get(f"/api/v1/organizations/{uuid4()}/control-modules")
    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_returns_versioned_platform_neutral_contract_for_authorized_actor() -> None:
    actor_id = uuid4()
    app = create_app(
        control_modules_use_case=ListControlModules(AllowAuthorizer(), StaticModuleCatalog())
    )

    @app.middleware("http")
    async def inject_test_principal(request, call_next):
        request.state.actor_id = actor_id
        return await call_next(request)

    client = TestClient(app)
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
