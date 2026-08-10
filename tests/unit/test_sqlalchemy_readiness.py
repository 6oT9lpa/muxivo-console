from contextlib import AbstractAsyncContextManager
from typing import Self

import pytest
from muxivo_console.infrastructure.persistence.readiness import SqlAlchemyDatabaseReadinessProbe


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self) -> None:
        self.statement = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    async def execute(self, statement) -> None:
        self.statement = statement


@pytest.mark.asyncio
async def test_database_probe_executes_a_constant_side_effect_free_query() -> None:
    session = FakeSession()
    probe = SqlAlchemyDatabaseReadinessProbe(lambda: session)

    await probe.check()

    assert str(session.statement) == "SELECT 1"
