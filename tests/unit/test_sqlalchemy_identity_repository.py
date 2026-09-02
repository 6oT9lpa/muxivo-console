from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.identity import UserStatus
from muxivo_console.infrastructure.persistence.identity_repository import (
    SqlAlchemyEmailPasswordAccountReader,
    SqlAlchemyUserEmailLookupReader,
)


class FakeResult:
    def __init__(self, row: tuple[object, object, object] | None) -> None:
        self.row = row

    def one_or_none(self) -> tuple[object, object, object] | None:
        return self.row

    def scalar_one_or_none(self) -> object | None:
        if self.row is None:
            return None
        return self.row[0]


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, row: tuple[object, object, object] | None) -> None:
        self.row = row
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
        return FakeResult(self.row)


@pytest.mark.asyncio
async def test_reads_minimal_active_account_projection_from_lookup_hash() -> None:
    user_id = uuid4()
    database_session = FakeSession((user_id, "active", "$argon2id$stored-hash"))

    account = await SqlAlchemyEmailPasswordAccountReader(
        lambda: database_session
    ).find_by_email_lookup_hash(email_lookup_hash="a" * 64)

    assert account.user_id == user_id
    assert account.status is UserStatus.ACTIVE
    assert account.password_hash == "$argon2id$stored-hash"
    assert database_session.statement is not None


@pytest.mark.asyncio
async def test_missing_or_corrupt_projection_is_rejected_fail_closed() -> None:
    missing = await SqlAlchemyEmailPasswordAccountReader(
        lambda: FakeSession(None)
    ).find_by_email_lookup_hash(email_lookup_hash="a" * 64)
    corrupt_status = await SqlAlchemyEmailPasswordAccountReader(
        lambda: FakeSession((uuid4(), "unknown", "$argon2id$stored-hash"))
    ).find_by_email_lookup_hash(email_lookup_hash="a" * 64)
    corrupt_hash = await SqlAlchemyEmailPasswordAccountReader(
        lambda: FakeSession((uuid4(), "active", "not-argon2"))
    ).find_by_email_lookup_hash(email_lookup_hash="a" * 64)

    assert missing is None
    assert corrupt_status is None
    assert corrupt_hash is None


@pytest.mark.asyncio
async def test_resolves_active_user_id_by_email_lookup_hash() -> None:
    user_id = uuid4()
    database_session = FakeSession((user_id, "active", "$argon2id$stored-hash"))

    resolved_user_id = await SqlAlchemyUserEmailLookupReader(
        lambda: database_session
    ).find_active_user_id_by_email_lookup_hash(email_lookup_hash="a" * 64)

    assert resolved_user_id == user_id
    assert database_session.statement is not None
