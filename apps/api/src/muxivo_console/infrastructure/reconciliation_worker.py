"""Runtime worker that periodically reconciles platform connection lifecycle state."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import IdentifierGenerator
from muxivo_console.application.reconcile_platform_connections import (
    ReconcilePlatformConnections,
    ReconcilePlatformConnectionsCommand,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PeriodicReconciliationWorkerSettings:
    system_actor_id: UUID
    interval_seconds: float = 300.0
    initial_delay_seconds: float = 10.0
    batch_limit: int = 100

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("Reconciliation interval must be positive.")
        if self.initial_delay_seconds < 0:
            raise ValueError("Reconciliation initial delay must not be negative.")
        if self.batch_limit <= 0:
            raise ValueError("Reconciliation batch limit must be positive.")


class PeriodicPlatformConnectionReconciliationWorker:
    """Starts one resilient asyncio task for periodic platform connection reconciliation."""

    def __init__(
        self,
        *,
        reconciler: ReconcilePlatformConnections,
        identifiers: IdentifierGenerator,
        settings: PeriodicReconciliationWorkerSettings,
    ) -> None:
        self._reconciler = reconciler
        self._identifiers = identifiers
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            logger.info("platform_connection.reconciliation_worker.already_started")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="platform-connection-reconciliation")
        logger.info(
            "platform_connection.reconciliation_worker.started",
            extra={
                "system_actor_id": str(self._settings.system_actor_id),
                "interval_seconds": self._settings.interval_seconds,
                "initial_delay_seconds": self._settings.initial_delay_seconds,
                "batch_limit": self._settings.batch_limit,
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
        logger.info(
            "platform_connection.reconciliation_worker.stopped",
            extra={"system_actor_id": str(self._settings.system_actor_id)},
        )

    async def run_once(self) -> None:
        correlation_id = self._identifiers.new()
        logger.info(
            "platform_connection.reconciliation_worker.tick_started",
            extra={
                "system_actor_id": str(self._settings.system_actor_id),
                "correlation_id": str(correlation_id),
                "batch_limit": self._settings.batch_limit,
            },
        )
        result = await self._reconciler.execute(
            ReconcilePlatformConnectionsCommand(
                system_actor_id=self._settings.system_actor_id,
                correlation_id=correlation_id,
                limit=self._settings.batch_limit,
            )
        )
        logger.info(
            "platform_connection.reconciliation_worker.tick_completed",
            extra={
                "system_actor_id": str(self._settings.system_actor_id),
                "correlation_id": str(correlation_id),
                "inspected": result.inspected,
                "changed": result.changed,
                "skipped": result.skipped,
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
                        "platform_connection.reconciliation_worker.tick_failed",
                        extra={
                            "system_actor_id": str(self._settings.system_actor_id),
                            "error_type": type(error).__name__,
                        },
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
