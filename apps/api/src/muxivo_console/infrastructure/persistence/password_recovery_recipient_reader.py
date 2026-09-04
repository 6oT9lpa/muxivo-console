"""SQLAlchemy adapter for resolving a protected recovery notification target."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.application.ports import EmailProtector
from muxivo_console.infrastructure.persistence.models import UserEmailRecord


class SqlAlchemyPasswordRecoveryRecipientReader:
    """Read and decrypt only the primary e-mail needed after password recovery."""

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        email_protector: EmailProtector,
    ) -> None:
        self._session_factory = session_factory
        self._email_protector = email_protector

    async def find_primary_email(self, *, user_id: UUID) -> str | None:
        statement = select(UserEmailRecord.email_ciphertext).where(
            UserEmailRecord.user_id == user_id,
            UserEmailRecord.is_primary.is_(True),
        )
        async with self._session_factory() as database_session:
            ciphertext = (await database_session.execute(statement)).scalar_one_or_none()
        if not isinstance(ciphertext, bytes):
            return None
        try:
            email = self._email_protector.decrypt(ciphertext)
        except (InvalidToken, TypeError, ValueError):
            return None
        return email if email else None
