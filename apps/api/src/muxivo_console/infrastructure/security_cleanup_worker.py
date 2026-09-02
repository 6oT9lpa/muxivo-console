"""Runtime worker that periodically enforces security-record retention."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta

from muxivo_console.application.cleanup_security_records import (
    CleanupSecurityRecords,
    CleanupSecurityRecordsCommand,
)
from muxivo_console.infrastructure.periodic_security_cleanup_worker_settings import (
    PeriodicSecurityCleanupWorkerSettings,
)

logger = logging.getLogger(__name__)


class PeriodicSecurityCleanupWorker:
    """Starts one resilient asyncio task for periodic retention cleanup."""

    def __init__(
        self,
        *,
        cleanup: CleanupSecurityRecords,
        settings: PeriodicSecurityCleanupWorkerSettings,
    ) -> None:
        self._cleanup = cleanup
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            logger.info("security.cleanup_worker.already_started")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="security-record-cleanup")
        logger.info(
            "security.cleanup_worker.started",
            extra={
                "interval_seconds": self._settings.interval_seconds,
                "initial_delay_seconds": self._settings.initial_delay_seconds,
                "session_retention_days": self._settings.session_retention_days,
                "password_recovery_retention_hours": (
                    self._settings.password_recovery_retention_hours
                ),
            },
        )

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        self._task = None
        logger.info("security.cleanup_worker.stopped")

    async def run_once(self) -> None:
        logger.info(
            "security.cleanup_worker.tick_started",
            extra={
                "session_retention_days": self._settings.session_retention_days,
                "password_recovery_retention_hours": (
                    self._settings.password_recovery_retention_hours
                ),
            },
        )
        result = await self._cleanup.execute(
            CleanupSecurityRecordsCommand(
                session_retention=timedelta(days=self._settings.session_retention_days),
                password_recovery_retention=timedelta(
                    hours=self._settings.password_recovery_retention_hours
                ),
            )
        )
        logger.info(
            "security.cleanup_worker.tick_completed",
            extra={
                "deleted_sessions": result.deleted_sessions,
                "deleted_password_recovery_transactions": (
                    result.deleted_password_recovery_transactions
                ),
            },
        )

    async def _run(self) -> None:
        try:
            await self._wait_or_stop(self._settings.initial_delay_seconds)
            while not self._stop_event.is_set():
                try:
                    await self.run_once()
                except Exception as error:
                    logger.error(
                        "security.cleanup_worker.tick_failed",
                        extra={"error_type": type(error).__name__},
                    )
                await self._wait_or_stop(self._settings.interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _wait_or_stop(self, delay_seconds: float) -> None:
        if delay_seconds <= 0:
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay_seconds)
        except TimeoutError:
            return


__all__ = [
    "PeriodicSecurityCleanupWorker",
    "PeriodicSecurityCleanupWorkerSettings",
]
