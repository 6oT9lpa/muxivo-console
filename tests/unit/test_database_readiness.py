import logging
from uuid import uuid4

import pytest
from muxivo_console.infrastructure.persistence.database_readiness import (
    SqlAlchemyDatabaseReadinessProbe,
)


class Session:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, statement):
        self.statement = statement
        if self.failure is not None:
            raise self.failure
        return object()


class SessionFactory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


@pytest.mark.asyncio
async def test_database_readiness_executes_a_constant_ping() -> None:
    session = Session()
    probe = SqlAlchemyDatabaseReadinessProbe(SessionFactory(session))

    ready = await probe.check(correlation_id=uuid4())

    assert ready is True
    assert str(session.statement) == "SELECT 1"


@pytest.mark.asyncio
async def test_database_readiness_fails_closed_without_exposing_database_error(caplog) -> None:
    session = Session(failure=RuntimeError("password=database-secret"))
    probe = SqlAlchemyDatabaseReadinessProbe(SessionFactory(session))
    caplog.set_level(
        logging.WARNING,
        logger="muxivo_console.infrastructure.persistence.database_readiness",
    )

    ready = await probe.check(correlation_id=uuid4())

    assert ready is False
    assert "database-secret" not in caplog.text
    assert "operations.readiness.database.failed" in caplog.text
