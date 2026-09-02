from datetime import UTC, datetime
from uuid import uuid4

import pytest
from muxivo_console.infrastructure.persistence.session_last_seen_repository import (
    SqlAlchemyAuthSessionLastSeenUpdater,
)


class Result:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class DatabaseSession:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def begin(self) -> Transaction:
        return Transaction()

    async def execute(self, statement) -> Result:
        self.statement = statement
        return Result(self.rowcount)


class SessionFactory:
    def __init__(self, session: DatabaseSession) -> None:
        self.session = session

    def __call__(self) -> DatabaseSession:
        return self.session


@pytest.mark.asyncio
@pytest.mark.parametrize(("rowcount", "expected"), ((1, True), (0, False)))
async def test_updates_last_seen_and_reports_atomic_result(rowcount: int, expected: bool) -> None:
    database_session = DatabaseSession(rowcount)
    updater = SqlAlchemyAuthSessionLastSeenUpdater(SessionFactory(database_session))
    timestamp = datetime(2026, 8, 9, tzinfo=UTC)

    updated = await updater.touch_last_seen(
        session_id=uuid4(),
        user_id=uuid4(),
        last_seen_at=timestamp,
    )

    assert updated is expected
    assert database_session.statement is not None
