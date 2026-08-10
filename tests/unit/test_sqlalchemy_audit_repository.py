from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.infrastructure.persistence.audit_repository import SqlAlchemyAuditEntryReader


class ScalarResults:
    def __init__(self, records) -> None:
        self._records = records

    def all(self):
        return self._records


class Result:
    def __init__(self, records) -> None:
        self._records = records

    def scalars(self) -> ScalarResults:
        return ScalarResults(self._records)


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, records) -> None:
        self.records = records
        self.statement = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    async def execute(self, statement) -> Result:
        self.statement = statement
        return Result(self.records)


@pytest.mark.asyncio
async def test_reader_scopes_cursor_and_filters_to_same_organization() -> None:
    organization_id = uuid4()
    cursor_id = uuid4()
    filtered_actor_id = uuid4()
    record = SimpleNamespace(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=filtered_actor_id,
        organization_id=organization_id,
        action="organization.member.role_changed",
        resource_type="organization_membership",
        resource_id=str(uuid4()),
        result="succeeded",
        created_at=datetime(2026, 8, 10, 18, 0, tzinfo=UTC),
    )
    session = FakeSession([record])
    reader = SqlAlchemyAuditEntryReader(lambda: session)

    entries = await reader.list_for_organization(
        organization_id=organization_id,
        after_event_id=cursor_id,
        actor_id=filtered_actor_id,
        action="organization.member.role_changed",
        resource_type="organization_membership",
        result="succeeded",
        limit=51,
    )

    assert entries[0].id == record.id
    sql = str(session.statement)
    assert sql.count("audit_events.organization_id") >= 2
    assert "audit_events.actor_id" in sql
    assert "audit_events.action" in sql
    assert "audit_events.resource_type" in sql
    assert "audit_events.result" in sql
    assert "ORDER BY audit_events.created_at DESC, audit_events.id DESC" in sql
