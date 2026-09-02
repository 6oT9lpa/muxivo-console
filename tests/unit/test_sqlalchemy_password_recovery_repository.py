from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    PasswordRecoveryTransactionRecord,
)
from muxivo_console.infrastructure.persistence.password_recovery_repository import (
    SqlAlchemyPasswordRecoveryRepository,
)


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


@dataclass(frozen=True, slots=True)
class FakeExecuteResult:
    recovery_record: PasswordRecoveryTransactionRecord | None = None
    rowcount: int = 0

    def scalar_one_or_none(self) -> PasswordRecoveryTransactionRecord | None:
        return self.recovery_record


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, results: list[FakeExecuteResult]) -> None:
        self.results = results
        self.transaction = FakeTransaction()
        self.executed: list[object] = []
        self.added: list[object] = []
        self.flushed = False

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

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.executed.append(statement)
        return self.results.pop(0)

    def add(self, record: object) -> None:
        self.added.append(record)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_password_recovery_completion_records_password_recovered_audit_event() -> None:
    completed_at = datetime(2026, 8, 22, 12, tzinfo=UTC)
    user_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    recovery_record = PasswordRecoveryTransactionRecord(
        id=uuid4(),
        user_id=user_id,
        token_hash="a" * 64,
        expires_at=completed_at + timedelta(minutes=5),
        consumed_at=None,
    )
    database_session = FakeSession(
        [
            FakeExecuteResult(recovery_record=recovery_record),
            FakeExecuteResult(rowcount=1),
            FakeExecuteResult(rowcount=2),
        ]
    )

    completed = await SqlAlchemyPasswordRecoveryRepository(lambda: database_session).complete(
        token_hash="a" * 64,
        password_hash="$argon2id$new-password-hash",
        completed_at=completed_at,
        audit_id=audit_id,
        correlation_id=correlation_id,
    )

    assert completed is True
    assert database_session.flushed is True
    assert len(database_session.executed) == 3
    assert len(database_session.added) == 1
    audit_event = database_session.added[0]
    assert isinstance(audit_event, AuditEventRecord)
    assert audit_event.id == audit_id
    assert audit_event.correlation_id == correlation_id
    assert audit_event.actor_id == user_id
    assert audit_event.action == "auth.password_recovered"
    assert audit_event.resource_type == "user"
    assert audit_event.resource_id == str(user_id)
