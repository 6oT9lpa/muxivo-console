from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.infrastructure.persistence.models import AuditEventRecord
from muxivo_console.infrastructure.persistence.session_repository import (
    SqlAlchemyAuthSessionRevoker,
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
    def __init__(self, matched_id: UUID | None) -> None:
        self.matched_id = matched_id

    def scalar_one_or_none(self) -> UUID | None:
        return self.matched_id


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, matched_id: UUID | None, integrity_error: bool = False) -> None:
        self.matched_id = matched_id
        self.integrity_error = integrity_error
        self.statement = None
        self.audit_record: AuditEventRecord | None = None
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

    async def execute(self, statement) -> FakeResult:
        self.statement = statement
        return FakeResult(self.matched_id)

    def add(self, record: AuditEventRecord) -> None:
        self.audit_record = record

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("UPDATE", {}, Exception("conflict"))


def audit(actor_id: UUID, session_id: UUID) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=actor_id,
        organization_id=None,
        action="auth.session_revoked",
        resource_type="auth_session",
        resource_id=str(session_id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_revoker_writes_audit_only_when_owned_active_session_was_updated() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    database_session = FakeSession(matched_id=session_id)
    event = audit(actor_id, session_id)

    revoked = await SqlAlchemyAuthSessionRevoker(lambda: database_session).revoke(
        session_id=session_id,
        user_id=actor_id,
        revoked_at=datetime(2026, 8, 10, 13, 30, tzinfo=UTC),
        audit_event=event,
    )

    assert revoked is True
    assert database_session.audit_record is not None
    assert database_session.audit_record.action == event.action
    assert database_session.audit_record.actor_id == actor_id
    assert "auth_sessions.revoked_at IS NULL" in str(database_session.statement)


@pytest.mark.asyncio
async def test_revoker_does_not_create_audit_when_no_session_matches() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    database_session = FakeSession(matched_id=None)

    revoked = await SqlAlchemyAuthSessionRevoker(lambda: database_session).revoke(
        session_id=session_id,
        user_id=actor_id,
        revoked_at=datetime(2026, 8, 10, 13, 30, tzinfo=UTC),
        audit_event=audit(actor_id, session_id),
    )

    assert revoked is False
    assert database_session.audit_record is None


@pytest.mark.asyncio
async def test_revoker_reduces_audit_persistence_conflict_to_safe_failure() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    database_session = FakeSession(matched_id=session_id, integrity_error=True)

    revoked = await SqlAlchemyAuthSessionRevoker(lambda: database_session).revoke(
        session_id=session_id,
        user_id=actor_id,
        revoked_at=datetime(2026, 8, 10, 13, 30, tzinfo=UTC),
        audit_event=audit(actor_id, session_id),
    )

    assert revoked is False
    assert database_session.transaction.exc_type is IntegrityError
