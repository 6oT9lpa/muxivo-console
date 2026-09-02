"""Atomic persistence adapter for throttled browser-session activity updates."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.infrastructure.persistence.models import AuthSessionRecord


class SqlAlchemyAuthSessionLastSeenUpdater:
    """Touches only a still-valid session owned by the authenticated user."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def touch_last_seen(
        self, *, session_id: UUID, user_id: UUID, last_seen_at: datetime
    ) -> bool:
        statement = (
            update(AuthSessionRecord)
            .where(
                AuthSessionRecord.id == session_id,
                AuthSessionRecord.user_id == user_id,
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at > last_seen_at,
            )
            .values(last_seen_at=last_seen_at)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(statement)
        return result.rowcount == 1


__all__ = ["SqlAlchemyAuthSessionLastSeenUpdater"]
