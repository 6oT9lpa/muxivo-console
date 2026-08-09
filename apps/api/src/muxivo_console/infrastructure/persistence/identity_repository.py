"""SQLAlchemy account projections for Console-owned first-party authentication."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.identity import EmailPasswordAccount, LoginIdentityProvider, UserStatus
from muxivo_console.infrastructure.persistence.models import (
    LoginIdentityRecord,
    PasswordCredentialRecord,
    UserEmailRecord,
    UserRecord,
)


class SqlAlchemyEmailPasswordAccountReader:
    """Read only the credential projection needed for a password verification."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None:
        statement = (
            select(UserRecord.id, UserRecord.status, PasswordCredentialRecord.password_hash)
            .join(UserEmailRecord, UserEmailRecord.user_id == UserRecord.id)
            .join(PasswordCredentialRecord, PasswordCredentialRecord.user_id == UserRecord.id)
            .where(UserEmailRecord.email_lookup_hash == email_lookup_hash)
        )
        async with self._session_factory() as database_session:
            result = await database_session.execute(statement)
            row = result.one_or_none()
        if row is None:
            return None
        try:
            return EmailPasswordAccount(
                user_id=row[0], status=UserStatus(row[1]), password_hash=row[2]
            )
        except ValueError:
            return None


class SqlAlchemyLoginIdentityReader:
    """Read a provider subject already verified and owned by this Console user."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_provider_subject(
        self, *, user_id: UUID, provider: LoginIdentityProvider
    ) -> str | None:
        statement = select(LoginIdentityRecord.provider_subject).where(
            LoginIdentityRecord.user_id == user_id,
            LoginIdentityRecord.provider == provider.value,
        )
        async with self._session_factory() as database_session:
            result = await database_session.execute(statement)
            value = result.scalar_one_or_none()
        return value if isinstance(value, str) and value else None
