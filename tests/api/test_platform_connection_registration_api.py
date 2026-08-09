from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_platform_connections import PlatformConnectionPage
from muxivo_console.application.register_platform_connection import (
    PlatformConnectionRegistrationRejectedError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
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

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class ConnectionRegistrationUseCase:
    def __init__(self, connection: PlatformConnection | None = None, rejects: bool = False) -> None:
        self.connection = connection
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise PlatformConnectionRegistrationRejectedError("Native authority denied.")
        return self.connection


class ConnectionListUseCase:
    def __init__(self, page: PlatformConnectionPage) -> None:
        self.page = page
        self.arguments = None

    async def execute(self, **arguments) -> PlatformConnectionPage:
        self.arguments = arguments
        return self.page


def headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def test_connection_registration_requires_session_and_csrf() -> None:
    organization_id = uuid4()
    client = TestClient(create_app())

    missing_csrf = client.post(
        f"/api/v1/organizations/{organization_id}/platform-connections",
        json={"platform": "discord", "external_resource_id": "123"},
    )
    missing_session = client.post(
        f"/api/v1/organizations/{organization_id}/platform-connections",
        json={"platform": "discord", "external_resource_id": "123"},
        headers={"Cookie": f"{CSRF_COOKIE_NAME}=csrf-token", CSRF_HEADER_NAME: "csrf-token"},
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json() == {"detail": "CSRF validation failed"}
    assert missing_session.status_code == 403
    assert missing_session.json() == {"detail": "Access denied"}


def test_connection_registration_uses_session_actor_and_neutral_contract() -> None:
    actor_id, organization_id, connection_id = uuid4(), uuid4(), uuid4()
    connection = PlatformConnection(
        id=connection_id,
        organization_id=organization_id,
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=ConnectionStatus.PENDING,
    )
    use_case = ConnectionRegistrationUseCase(connection)
    client = TestClient(
        create_app(
            platform_connection_registration_use_case=use_case,
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.post(
        f"/api/v1/organizations/{organization_id}/platform-connections",
        json={"platform": "discord", "external_resource_id": " 123456789012345678 "},
        headers=headers(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(connection_id),
        "organization_id": str(organization_id),
        "platform": "discord",
        "external_resource_id": "123456789012345678",
        "status": "pending",
    }
    assert use_case.command.actor_id == actor_id
    assert use_case.command.organization_id == organization_id
    assert use_case.command.external_resource_id == "123456789012345678"
    assert isinstance(use_case.command.correlation_id, UUID)


def test_connection_registration_hides_native_rejection_reason() -> None:
    client = TestClient(
        create_app(
            platform_connection_registration_use_case=ConnectionRegistrationUseCase(rejects=True),
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.post(
        f"/api/v1/organizations/{uuid4()}/platform-connections",
        json={"platform": "discord", "external_resource_id": "123"},
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Platform connection registration failed"}


def test_connection_list_returns_cursor_paginated_neutral_contract() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    first = PlatformConnection(
        id=uuid4(),
        organization_id=organization_id,
        platform=Platform.DISCORD,
        external_resource_id="123",
        status=ConnectionStatus.ACTIVE,
    )
    next_cursor = uuid4()
    use_case = ConnectionListUseCase(PlatformConnectionPage((first,), next_cursor))
    client = TestClient(
        create_app(
            platform_connections_use_case=use_case,
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.get(
        f"/api/v1/organizations/{organization_id}/platform-connections?cursor={first.id}&limit=20",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(first.id),
                "organization_id": str(organization_id),
                "platform": "discord",
                "external_resource_id": "123",
                "status": "active",
            }
        ],
        "next_cursor": str(next_cursor),
    }
    assert use_case.arguments == {
        "actor_id": actor_id,
        "organization_id": organization_id,
        "after_id": first.id,
        "limit": 20,
    }
