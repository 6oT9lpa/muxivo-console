from uuid import uuid4

import pytest
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.list_platform_connections import ListPlatformConnections
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection


class Authorizer:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(self.allowed)


class Connections:
    def __init__(self, items: tuple[PlatformConnection, ...]) -> None:
        self.items = items
        self.arguments = None

    async def list_for_organization(self, **arguments) -> tuple[PlatformConnection, ...]:
        self.arguments = arguments
        return self.items


def connection() -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123",
        status=ConnectionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_authorized_reader_uses_keyset_limit_and_returns_next_cursor() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    first, second, third = connection(), connection(), connection()
    connections = Connections((first, second, third))
    authorizer = Authorizer(True)

    page = await ListPlatformConnections(authorizer, connections).execute(
        actor_id=actor_id, organization_id=organization_id, after_id=first.id, limit=2
    )

    assert page.items == (first, second)
    assert page.next_cursor == second.id
    assert connections.arguments == {
        "organization_id": organization_id,
        "after_id": first.id,
        "limit": 3,
    }
    assert authorizer.request.resource.value == "console.platform_connections"
    assert authorizer.request.action.value == "read"


@pytest.mark.asyncio
async def test_denied_reader_never_queries_persistence() -> None:
    connections = Connections(())

    with pytest.raises(AccessDeniedError):
        await ListPlatformConnections(Authorizer(False), connections).execute(
            actor_id=uuid4(), organization_id=uuid4()
        )

    assert connections.arguments is None


@pytest.mark.asyncio
async def test_rejects_unbounded_page_size() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        await ListPlatformConnections(Authorizer(True), Connections(())).execute(
            actor_id=uuid4(), organization_id=uuid4(), limit=101
        )
