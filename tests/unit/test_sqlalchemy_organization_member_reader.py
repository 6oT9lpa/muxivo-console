from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace, TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.organizations import OrganizationRole
from muxivo_console.infrastructure.persistence.organization_repository import (
    SqlAlchemyOrganizationMemberReader,
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


@pytest.mark.asyncio
async def test_member_reader_scopes_to_tenant_and_discards_malformed_rows() -> None:
    organization_id = uuid4()
    cursor = uuid4()
    valid_membership = SimpleNamespace(id=uuid4(), user_id=uuid4(), role="admin")
    invalid_membership = SimpleNamespace(id=uuid4(), user_id=uuid4(), role="unexpected-role")
    database_session = FakeSession(
        [(valid_membership, "Admin User"), (invalid_membership, "Malformed")]
    )

    members = await SqlAlchemyOrganizationMemberReader(
        lambda: database_session
    ).list_for_organization(
        organization_id=organization_id,
        after_membership_id=cursor,
        limit=3,
    )

    assert len(members) == 1
    assert members[0].membership_id == valid_membership.id
    assert members[0].user_id == valid_membership.user_id
    assert members[0].display_name == "Admin User"
    assert members[0].role is OrganizationRole.ADMIN
    sql = str(database_session.statement)
    assert "organization_memberships.organization_id" in sql
    assert "organization_memberships.id >" in sql
    assert "ORDER BY organization_memberships.id" in sql
    assert "LIMIT" in sql
