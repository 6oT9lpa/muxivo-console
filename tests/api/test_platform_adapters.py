from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_platform_adapters import ListPlatformAdapters
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.platforms import (
    PlatformAdapterCapability,
    PlatformAdapterDescriptor,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app
from muxivo_console.presentation.platform_adapters import create_platform_adapter_router


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class AdapterCatalog:
    def list_configured(self):
        return (
            PlatformAdapterDescriptor(
                platform=Platform.DISCORD,
                capabilities=frozenset(
                    {
                        PlatformAdapterCapability.CONNECTION_REGISTRATION,
                        PlatformAdapterCapability.HEALTH,
                    }
                ),
            ),
        )


def client_for(principal: BrowserSessionPrincipal | None) -> TestClient:
    app = create_app(session_resolver=SessionResolver(principal))
    app.include_router(create_platform_adapter_router(ListPlatformAdapters(AdapterCatalog())))
    return TestClient(app, base_url="https://testserver")


def test_adapter_capabilities_are_authenticated_and_deterministic() -> None:
    principal = BrowserSessionPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )
    client = client_for(principal)

    response = client.get(
        "/api/v1/platform-adapters",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "platform": "discord",
                "capabilities": ["connection_registration", "health"],
            }
        ]
    }


def test_adapter_capabilities_are_not_exposed_to_anonymous_browser() -> None:
    response = client_for(None).get("/api/v1/platform-adapters")

    assert response.status_code == 401
