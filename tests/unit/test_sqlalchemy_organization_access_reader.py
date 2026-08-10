from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace, TracebackType
from typing import Self
from uuid import UUID, uuid4

import pytest
from muxivo_console.domain.organizations import OrganizationRole
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationAccessReader,
)


class FakeResult:
    def __init__(self, rows: list[tuple[SimpleNamespace, str]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[SimpleNamespace, str]]:
        return self._rows


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, rows: list[tuple[SimpleNamespace, str]]) -> None:
        self._rows = rows
        self.statement = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    async def execute(self, statement) -> FakeResult:
        self.statement = statement
        return FakeResult(self._rows)


def organization(identifier: UUID, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=identifier, name=name, slug=name.lower().replace(" ", "-"))


@pytest.mark.asyncio
async def test_access_reader_scopes_query_to_actor_and_keyset_cursor() -> None:
    actor_id = uuid4()
    cursor = uuid4()
    visible_id = uuid4()
    database_session = FakeSession(
        [
            (organization(visible_id, "Creator Team"), "admin"),
            (organization(uuid4(), "Malformed"), "unexpected-role"),
        ]
    )

    accesses = await SqlAlchemyOrganizationAccessReader(lambda: database_session).list_for_actor(
        actor_id=actor_id,
        after_organization_id=cursor,
        limit=3,
    )

    assert len(accesses) == 1
    assert accesses[0].organization.id == visible_id
    assert accesses[0].role is OrganizationRole.ADMIN
    sql = str(database_session.statement)
    assert "organization_memberships.user_id" in sql
    assert "organizations.id >" in sql
    assert "ORDER BY organizations.id" in sql
    assert "LIMIT" in sql
