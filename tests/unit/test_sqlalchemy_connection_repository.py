from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.infrastructure.persistence.connection_repository import (
    SqlAlchemyPlatformConnectionWriter,
)
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    PlatformConnectionLifecycleIdempotencyRecord,
    PlatformConnectionRecord,
)
from sqlalchemy.exc import IntegrityError


@dataclass
class FakeTransaction(AbstractAsyncContextManager[None]):
    exc_type: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.exc_type = exc_type
        return False


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, integrity_error: bool = False, rowcount: int = 1) -> None:
        self.integrity_error = integrity_error
        self.rowcount = rowcount
        self.records: tuple[object, ...] = ()
        self.transaction = FakeTransaction()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return self.transaction

    def add_all(self, records: tuple[object, ...]) -> None:
        self.records = records

    def add(self, record: object) -> None:
        self.records = (*self.records, record)

    async def execute(self, _) -> object:
        return FakeExecuteResult(self.rowcount)

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))


@dataclass(frozen=True, slots=True)
class FakeExecuteResult:
    rowcount: int


def connection() -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=ConnectionStatus.PENDING,
        granted_capabilities=("discord.guild.read", "discord.guild.manage"),
    )


def audit_event(stored: PlatformConnection) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=uuid4(),
        organization_id=stored.organization_id,
        action="platform_connection.connect",
        resource_type="platform_connection",
        resource_id=str(stored.id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_writes_non_secret_connection_metadata_and_audit_atomically() -> None:
    database_session = FakeSession()
    stored = connection()

    created = await SqlAlchemyPlatformConnectionWriter(lambda: database_session).create(
        connection=stored, audit_event=audit_event(stored)
    )

    assert created is True
    assert tuple(type(record) for record in database_session.records) == (
        PlatformConnectionRecord,
        AuditEventRecord,
    )
    connection_record = database_session.records[0]
    assert connection_record.platform == "discord"
    assert connection_record.external_resource_id == "123456789012345678"
    assert connection_record.status == "pending"
    assert connection_record.granted_capabilities == {
        "discord.guild.read": True,
        "discord.guild.manage": True,
    }
    assert not hasattr(connection_record, "credential")


@pytest.mark.asyncio
async def test_conflict_becomes_safe_non_partial_failure() -> None:
    database_session = FakeSession(integrity_error=True)
    stored = connection()

    created = await SqlAlchemyPlatformConnectionWriter(lambda: database_session).create(
        connection=stored, audit_event=audit_event(stored)
    )

    assert created is False
    assert database_session.transaction.exc_type is IntegrityError


@pytest.mark.asyncio
async def test_status_update_persists_idempotency_result_and_audit_atomically() -> None:
    database_session = FakeSession()
    stored = connection().transition_to(
        ConnectionStatus.ACTIVE,
        reason=ConnectionStatusReason.HEALTHY,
    )

    saved = await SqlAlchemyPlatformConnectionWriter(lambda: database_session).update_status(
        connection=stored,
        audit_event=audit_event(stored),
        idempotency_key="retry-1",
        idempotency_action="reauthorize",
    )

    assert saved is True
    assert tuple(type(record) for record in database_session.records) == (
        PlatformConnectionLifecycleIdempotencyRecord,
        AuditEventRecord,
    )
    idempotency_record = database_session.records[0]
    assert idempotency_record.organization_id == stored.organization_id
    assert idempotency_record.connection_id == stored.id
    assert idempotency_record.idempotency_key == "retry-1"
    assert idempotency_record.action == "reauthorize"
    assert idempotency_record.result_status == "active"
    assert idempotency_record.result_reason == "healthy"
