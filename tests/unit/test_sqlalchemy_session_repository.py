from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel
from muxivo_console.infrastructure.persistence.models import AuditEventRecord, AuthSessionRecord
from muxivo_console.infrastructure.persistence.session_repository import (
    SqlAlchemyAuthSessionReader,
    SqlAlchemyAuthSessionReauthenticationWriter,
    SqlAlchemyAuthSessionWriter,
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


class FakeResult:
    def __init__(self, record: AuthSessionRecord | None, rowcount: int = 0) -> None:
        self.record = record
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> AuthSessionRecord | None:
        return self.record


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(
        self,
        *,
        record: AuthSessionRecord | None = None,
        integrity_error: bool = False,
        rowcount: int = 0,
    ) -> None:
        self.record = record
        self.integrity_error = integrity_error
        self.rowcount = rowcount
        self.records: tuple[object, ...] = ()
        self.added_record: object | None = None
        self.transaction = FakeTransaction()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return self.transaction

    def add_all(self, records: tuple[object, ...]) -> None:
        self.records = records

    def add(self, record: object) -> None:
        self.added_record = record

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))

    async def execute(self, statement) -> FakeResult:
        return FakeResult(self.record, self.rowcount)


def session() -> AuthSession:
    return AuthSession(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="a" * 64,
        expires_at=datetime(2026, 8, 10, tzinfo=UTC),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )


def audit_event(session_value: AuthSession) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=session_value.user_id,
        organization_id=None,
        action="auth.session_created",
        resource_type="auth_session",
        resource_id=str(session_value.id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_writer_stores_hash_only_session_and_audit_in_one_transaction() -> None:
    database_session = FakeSession()
    stored = session()

    created = await SqlAlchemyAuthSessionWriter(lambda: database_session).create(
        session=stored, audit_event=audit_event(stored)
    )

    assert created is True
    assert database_session.transaction.exc_type is None
    assert tuple(type(record) for record in database_session.records) == (
        AuthSessionRecord,
        AuditEventRecord,
    )
    assert database_session.records[0].token_hash == "a" * 64


@pytest.mark.asyncio
async def test_writer_reduces_persistence_conflict_to_safe_failure() -> None:
    database_session = FakeSession(integrity_error=True)
    stored = session()

    created = await SqlAlchemyAuthSessionWriter(lambda: database_session).create(
        session=stored, audit_event=audit_event(stored)
    )

    assert created is False
    assert database_session.transaction.exc_type is IntegrityError


@pytest.mark.asyncio
async def test_reader_maps_valid_stored_session_and_denies_unknown_assurance_level() -> None:
    stored = session()
    record = AuthSessionRecord(
        id=stored.id,
        user_id=stored.user_id,
        token_hash=stored.token_hash,
        expires_at=stored.expires_at,
        revoked_at=None,
        assurance_level=stored.assurance_level.value,
    )
    found = await SqlAlchemyAuthSessionReader(
        lambda: FakeSession(record=record)
    ).find_by_token_hash(token_hash=stored.token_hash)
    record.assurance_level = "unexpected"
    unknown_assurance = await SqlAlchemyAuthSessionReader(
        lambda: FakeSession(record=record)
    ).find_by_token_hash(token_hash=stored.token_hash)

    assert found == stored
    assert unknown_assurance is None


@pytest.mark.asyncio
async def test_reauthentication_writer_updates_current_session_and_audit() -> None:
    stored = session()
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    database_session = FakeSession(rowcount=1)
    event = AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=stored.user_id,
        organization_id=None,
        action="auth.session_reauthenticated",
        resource_type="auth_session",
        resource_id=str(stored.id),
        result="succeeded",
    )

    updated = await SqlAlchemyAuthSessionReauthenticationWriter(
        lambda: database_session
    ).reauthenticate(
        session_id=stored.id,
        user_id=stored.user_id,
        authenticated_at=now,
        audit_event=event,
    )

    assert updated is True
    assert isinstance(database_session.added_record, AuditEventRecord)
    assert database_session.added_record.action == "auth.session_reauthenticated"
