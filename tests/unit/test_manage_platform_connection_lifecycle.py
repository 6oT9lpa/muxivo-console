from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.manage_platform_connection_lifecycle import (
    ManagePlatformConnectionLifecycle,
    ManagePlatformConnectionLifecycleCommand,
    PlatformConnectionLifecycleAction,
    PlatformConnectionLifecycleRejectedError,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import (
    ConnectionStatus,
    PlatformConnection,
    PlatformConnectionLifecycleIdempotencyResult,
)


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


class ConnectionReader:
    def __init__(self, connection: PlatformConnection | None) -> None:
        self.connection = connection

    async def find_for_organization(
        self, *, organization_id: UUID, connection_id: UUID
    ) -> PlatformConnection | None:
        if self.connection is None or self.connection.id != connection_id:
            return None
        return self.connection


class LifecycleWriter:
    def __init__(
        self,
        saved: bool = True,
        idempotent_result: PlatformConnectionLifecycleIdempotencyResult | None = None,
    ) -> None:
        self.saved = saved
        self.idempotent_result = idempotent_result
        self.connection: PlatformConnection | None = None
        self.audit_event: AuditEvent | None = None
        self.idempotency_key: str | None = None
        self.idempotency_action: str | None = None

    async def update_status(
        self,
        *,
        connection: PlatformConnection,
        audit_event: AuditEvent,
        idempotency_key: str | None = None,
        idempotency_action: str | None = None,
    ) -> bool:
        self.connection = connection
        self.audit_event = audit_event
        self.idempotency_key = idempotency_key
        self.idempotency_action = idempotency_action
        return self.saved

    async def find_idempotent_lifecycle_result(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> PlatformConnectionLifecycleIdempotencyResult | None:
        if (
            self.idempotent_result is None
            or self.idempotent_result.organization_id != organization_id
        ):
            return None
        return self.idempotent_result


def connection(status: ConnectionStatus) -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123",
        status=status,
    )


def command(
    existing: PlatformConnection, action: PlatformConnectionLifecycleAction
) -> ManagePlatformConnectionLifecycleCommand:
    return ManagePlatformConnectionLifecycleCommand(
        actor_id=uuid4(),
        organization_id=existing.organization_id,
        connection_id=existing.id,
        action=action,
        correlation_id=uuid4(),
        idempotency_key="retry-key",
    )


@pytest.mark.asyncio
async def test_revoke_moves_active_connection_to_reauth_required_and_records_audit() -> None:
    existing = connection(ConnectionStatus.ACTIVE)
    audit_id = uuid4()
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([audit_id]),
    )

    updated = await use_case.execute(command(existing, PlatformConnectionLifecycleAction.REVOKE))

    assert updated.status is ConnectionStatus.REAUTH_REQUIRED
    assert updated.status_reason is ConnectionStatusReason.REVOKED
    assert writer.connection == updated
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "platform_connection.revoke"
    assert writer.audit_event.resource_id == str(existing.id)
    assert writer.idempotency_key == "retry-key"
    assert writer.idempotency_action == "revoke"


@pytest.mark.asyncio
async def test_lifecycle_replays_persisted_idempotent_result_without_new_audit() -> None:
    existing = connection(ConnectionStatus.REAUTH_REQUIRED)
    writer = LifecycleWriter(
        idempotent_result=PlatformConnectionLifecycleIdempotencyResult(
            organization_id=existing.organization_id,
            connection_id=existing.id,
            action="revoke",
            result_status=ConnectionStatus.REAUTH_REQUIRED,
        )
    )
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )

    updated = await use_case.execute(command(existing, PlatformConnectionLifecycleAction.REVOKE))

    assert updated == existing
    assert writer.connection is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_reauthorize_moves_connection_to_active_and_records_audit() -> None:
    existing = connection(ConnectionStatus.REAUTH_REQUIRED)
    audit_id = uuid4()
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([audit_id]),
    )

    updated = await use_case.execute(
        command(existing, PlatformConnectionLifecycleAction.REAUTHORIZE)
    )

    assert updated.status is ConnectionStatus.ACTIVE
    assert updated.status_reason is ConnectionStatusReason.REAUTHORIZED
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "platform_connection.reauthorize"
    assert writer.audit_event.resource_id == str(existing.id)
    assert writer.idempotency_action == "reauthorize"


@pytest.mark.asyncio
async def test_disconnect_moves_connection_to_disconnected_and_records_audit() -> None:
    existing = connection(ConnectionStatus.ACTIVE)
    audit_id = uuid4()
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([audit_id]),
    )

    updated = await use_case.execute(
        command(existing, PlatformConnectionLifecycleAction.DISCONNECT)
    )

    assert updated.status is ConnectionStatus.DISCONNECTED
    assert updated.status_reason is ConnectionStatusReason.DISCONNECTED
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.action == "platform_connection.disconnect"
    assert writer.audit_event.resource_id == str(existing.id)
    assert writer.idempotency_action == "disconnect"


@pytest.mark.asyncio
async def test_lifecycle_rejects_conflicting_idempotency_key_without_writing() -> None:
    existing = connection(ConnectionStatus.ACTIVE)
    writer = LifecycleWriter(
        idempotent_result=PlatformConnectionLifecycleIdempotencyResult(
            organization_id=existing.organization_id,
            connection_id=existing.id,
            action="disconnect",
            result_status=ConnectionStatus.DISCONNECTED,
        )
    )
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )

    with pytest.raises(PlatformConnectionLifecycleRejectedError):
        await use_case.execute(command(existing, PlatformConnectionLifecycleAction.REVOKE))

    assert writer.connection is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_lifecycle_rejects_overlong_idempotency_key_without_writing() -> None:
    existing = connection(ConnectionStatus.ACTIVE)
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )
    request = ManagePlatformConnectionLifecycleCommand(
        actor_id=uuid4(),
        organization_id=existing.organization_id,
        connection_id=existing.id,
        action=PlatformConnectionLifecycleAction.REVOKE,
        correlation_id=uuid4(),
        idempotency_key="x" * 129,
    )

    with pytest.raises(PlatformConnectionLifecycleRejectedError):
        await use_case.execute(request)

    assert writer.connection is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_disconnect_is_retry_safe_when_connection_is_already_disconnected() -> None:
    existing = connection(ConnectionStatus.DISCONNECTED)
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )

    updated = await use_case.execute(
        command(existing, PlatformConnectionLifecycleAction.DISCONNECT)
    )

    assert updated == existing
    assert writer.connection is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_invalid_transition_fails_closed_without_writing() -> None:
    existing = connection(ConnectionStatus.DISCONNECTED)
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(True),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )

    with pytest.raises(PlatformConnectionLifecycleRejectedError):
        await use_case.execute(command(existing, PlatformConnectionLifecycleAction.REAUTHORIZE))

    assert writer.connection is None
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_denied_actor_does_not_read_or_write_connection() -> None:
    existing = connection(ConnectionStatus.ACTIVE)
    writer = LifecycleWriter()
    use_case = ManagePlatformConnectionLifecycle(
        authorizer=Authorizer(False),
        connections=ConnectionReader(existing),
        lifecycle=writer,
        identifiers=SequenceIdentifiers([uuid4()]),
    )

    with pytest.raises(PlatformConnectionLifecycleRejectedError):
        await use_case.execute(command(existing, PlatformConnectionLifecycleAction.DISCONNECT))

    assert writer.connection is None
