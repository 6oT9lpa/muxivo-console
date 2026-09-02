"""Database readiness adapter for the Console operations boundary."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SqlAlchemyDatabaseReadinessProbe:
    """Run a bounded database ping without exposing provider error details."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def check(self, *, correlation_id: UUID) -> bool:
        logger.info(
            "operations.readiness.database.started",
            extra={"correlation_id": str(correlation_id)},
        )
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as error:
            logger.warning(
                "operations.readiness.database.failed",
                extra={
                    "correlation_id": str(correlation_id),
                    "error_type": type(error).__name__,
                },
            )
            return False
        logger.info(
            "operations.readiness.database.completed",
            extra={"correlation_id": str(correlation_id)},
        )
        return True


__all__ = ["SqlAlchemyDatabaseReadinessProbe"]
