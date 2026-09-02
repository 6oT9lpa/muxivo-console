from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import pytest
from muxivo_console.infrastructure.persistence.security_cleanup_repository import (
    SqlAlchemySecurityRecordCleaner,
)


@dataclass
class FakeTransaction(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class FakeExecuteResult:
    rowcount: int


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, rowcounts: list[int]) -> None:
        self.rowcounts = rowcounts
        self.executed: list[object] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.executed.append(statement)
        return FakeExecuteResult(self.rowcounts.pop(0))


@pytest.mark.asyncio
async def test_security_cleanup_repository_returns_deleted_session_count() -> None:
    database_session = FakeSession([5])
    cleaner = SqlAlchemySecurityRecordCleaner(lambda: database_session)

    deleted = await cleaner.delete_expired_or_revoked_sessions(before=object())

    assert deleted == 5
    assert len(database_session.executed) == 1


@pytest.mark.asyncio
async def test_security_cleanup_repository_returns_deleted_recovery_count() -> None:
    database_session = FakeSession([2])
    cleaner = SqlAlchemySecurityRecordCleaner(lambda: database_session)

    deleted = await cleaner.delete_consumed_or_expired_password_recovery_transactions(
        before=object()
    )

    assert deleted == 2
    assert len(database_session.executed) == 1
