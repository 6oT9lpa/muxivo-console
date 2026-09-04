from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.infrastructure.persistence.identity_unlink_writer import (
    SqlAlchemyLoginIdentityUnlinkWriter,
)
from muxivo_console.infrastructure.persistence.models import AuditEventRecord
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


@dataclass(frozen=True, slots=True)
class FakeExecuteResult:
    rowcount: int


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, *, integrity_error: bool = False, rowcount: int = 1) -> None:
        self.integrity_error = integrity_error
        self.rowcount = rowcount
        self.records: list[object] = []
        self.transaction = FakeTransaction()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return self.transaction

    async def execute(self, _) -> FakeExecuteResult:
        return FakeExecuteResult(self.rowcount)

    def add(self, record: object) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("DELETE", {}, Exception("constraint"))


def audit_event(user_id) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=user_id,
        organization_id=None,
        action="identity.unlink",
        resource_type="login_identity",
        resource_id=str(uuid4()),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_unlinks_provider_identity_and_records_audit_atomically() -> None:
    session = FakeSession()
    user_id = uuid4()

    unlinked = await SqlAlchemyLoginIdentityUnlinkWriter(lambda: session).unlink(
        identity_id=uuid4(), user_id=user_id, audit_event=audit_event(user_id)
    )

    assert unlinked is True
    assert session.transaction.exc_type is None
    assert tuple(type(record) for record in session.records) == (AuditEventRecord,)
    assert session.records[0].action == "identity.unlink"


@pytest.mark.asyncio
async def test_missing_identity_is_a_safe_non_partial_failure() -> None:
    session = FakeSession(rowcount=0)
    user_id = uuid4()

    unlinked = await SqlAlchemyLoginIdentityUnlinkWriter(lambda: session).unlink(
        identity_id=uuid4(), user_id=user_id, audit_event=audit_event(user_id)
    )

    assert unlinked is False
    assert session.records == []


@pytest.mark.asyncio
async def test_database_conflict_is_reduced_to_safe_failure() -> None:
    session = FakeSession(integrity_error=True)
    user_id = uuid4()

    unlinked = await SqlAlchemyLoginIdentityUnlinkWriter(lambda: session).unlink(
        identity_id=uuid4(), user_id=user_id, audit_event=audit_event(user_id)
    )

    assert unlinked is False
    assert session.transaction.exc_type is IntegrityError
