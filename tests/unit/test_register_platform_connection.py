from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.register_platform_connection import (
    PlatformConnectionRegistrationRejectedError,
    RegisterPlatformConnection,
    RegisterPlatformConnectionCommand,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection


class SequenceIdentifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class Authorizer:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.request: AuthorizationRequest | None = None

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        self.request = request
        return AuthorizationDecision(self.allowed)


class Verifier:
    def __init__(self, verified: bool) -> None:
        self.verified = verified
        self.arguments = None

    async def verify_registration(self, **arguments) -> bool:
        self.arguments = arguments
        return self.verified


class ConnectionWriter:
    def __init__(self, created: bool = True) -> None:
        self.created = created
        self.connection: PlatformConnection | None = None
        self.audit_event: AuditEvent | None = None

    async def create(self, *, connection: PlatformConnection, audit_event: AuditEvent) -> bool:
        self.connection = connection
        self.audit_event = audit_event
        return self.created


def command() -> RegisterPlatformConnectionCommand:
    return RegisterPlatformConnectionCommand(
        actor_id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id=" 123456789012345678 ",
        correlation_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_registers_only_a_platform_verified_non_secret_pending_connection() -> None:
    requested = command()
    authorizer = Authorizer(True)
    verifier = Verifier(True)
    writer = ConnectionWriter()
    connection_id, audit_id = uuid4(), uuid4()
    use_case = RegisterPlatformConnection(
        authorizer, verifier, SequenceIdentifiers([connection_id, audit_id]), writer
    )

    connection = await use_case.execute(requested)

    assert connection.id == connection_id
    assert connection.status is ConnectionStatus.PENDING
    assert connection.external_resource_id == "123456789012345678"
    assert verifier.arguments == {
        "actor_id": requested.actor_id,
        "organization_id": requested.organization_id,
        "platform": Platform.DISCORD,
        "external_resource_id": "123456789012345678",
        "correlation_id": requested.correlation_id,
    }
    assert authorizer.request.resource.value == "console.platform_connections"
    assert writer.audit_event.action == "platform_connection.register"
    assert writer.audit_event.resource_id == str(connection_id)


@pytest.mark.asyncio
async def test_does_not_call_platform_or_write_connection_when_console_rbac_denies() -> None:
    verifier = Verifier(True)
    writer = ConnectionWriter()
    use_case = RegisterPlatformConnection(
        Authorizer(False), verifier, SequenceIdentifiers([uuid4(), uuid4()]), writer
    )

    with pytest.raises(PlatformConnectionRegistrationRejectedError):
        await use_case.execute(command())

    assert verifier.arguments is None
    assert writer.connection is None


@pytest.mark.asyncio
async def test_does_not_write_connection_without_platform_native_verification() -> None:
    writer = ConnectionWriter()
    use_case = RegisterPlatformConnection(
        Authorizer(True), Verifier(False), SequenceIdentifiers([uuid4(), uuid4()]), writer
    )

    with pytest.raises(PlatformConnectionRegistrationRejectedError):
        await use_case.execute(command())

    assert writer.connection is None
