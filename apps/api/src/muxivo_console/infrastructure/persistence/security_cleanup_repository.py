"""SQLAlchemy cleanup adapter for retained authentication security records."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.infrastructure.persistence.models import (
    AuthSessionRecord,
    PasswordRecoveryTransactionRecord,
)


class SqlAlchemySecurityRecordCleaner:
    """Delete expired security records without touching active credentials or audit logs."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def delete_expired_or_revoked_sessions(self, *, before) -> int:
        statement = delete(AuthSessionRecord).where(
            or_(
                AuthSessionRecord.expires_at < before,
                AuthSessionRecord.revoked_at < before,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
        return int(result.rowcount or 0)

    async def delete_consumed_or_expired_password_recovery_transactions(
        self, *, before
    ) -> int:
        statement = delete(PasswordRecoveryTransactionRecord).where(
            or_(
                PasswordRecoveryTransactionRecord.expires_at < before,
                PasswordRecoveryTransactionRecord.consumed_at < before,
            )
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
        return int(result.rowcount or 0)
