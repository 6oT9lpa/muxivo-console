from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.reconcile_platform_connections import (
    ReconcilePlatformConnectionsCommand,
    ReconcilePlatformConnectionsResult,
)
from muxivo_console.infrastructure.reconciliation_worker import (
    PeriodicPlatformConnectionReconciliationWorker,
    PeriodicReconciliationWorkerSettings,
)


@dataclass(slots=True)
class FakeIdentifiers:
    correlation_id: UUID

    def new(self) -> UUID:
        return self.correlation_id


@dataclass(slots=True)
class FakeReconciler:
    command: ReconcilePlatformConnectionsCommand | None = None
    raises: bool = False

    async def execute(
        self, command: ReconcilePlatformConnectionsCommand
    ) -> ReconcilePlatformConnectionsResult:
        self.command = command
        if self.raises:
            raise RuntimeError("probe failed")
        return ReconcilePlatformConnectionsResult(inspected=3, changed=1, skipped=2)


@pytest.mark.asyncio
async def test_reconciliation_worker_run_once_delegates_with_system_actor_and_limit() -> None:
    system_actor_id = uuid4()
    correlation_id = uuid4()
    reconciler = FakeReconciler()
    worker = PeriodicPlatformConnectionReconciliationWorker(
        reconciler=reconciler,
        identifiers=FakeIdentifiers(correlation_id),
        settings=PeriodicReconciliationWorkerSettings(
            system_actor_id=system_actor_id,
            interval_seconds=60,
            initial_delay_seconds=0,
            batch_limit=25,
        ),
    )

    await worker.run_once()

    assert reconciler.command == ReconcilePlatformConnectionsCommand(
        system_actor_id=system_actor_id,
        correlation_id=correlation_id,
        limit=25,
    )


@pytest.mark.asyncio
async def test_reconciliation_worker_start_and_stop_without_waiting_for_long_interval() -> None:
    worker = PeriodicPlatformConnectionReconciliationWorker(
        reconciler=FakeReconciler(),
        identifiers=FakeIdentifiers(uuid4()),
        settings=PeriodicReconciliationWorkerSettings(
            system_actor_id=uuid4(),
            interval_seconds=3600,
            initial_delay_seconds=3600,
            batch_limit=10,
        ),
    )

    await worker.start()
    await worker.stop()


def test_reconciliation_worker_settings_validate_runtime_values() -> None:
    with pytest.raises(ValueError, match="interval"):
        PeriodicReconciliationWorkerSettings(system_actor_id=uuid4(), interval_seconds=0)
    with pytest.raises(ValueError, match="initial delay"):
        PeriodicReconciliationWorkerSettings(system_actor_id=uuid4(), initial_delay_seconds=-1)
    with pytest.raises(ValueError, match="batch limit"):
        PeriodicReconciliationWorkerSettings(system_actor_id=uuid4(), batch_limit=0)
