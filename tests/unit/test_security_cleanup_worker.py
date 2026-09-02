import asyncio
from datetime import timedelta

import pytest
from muxivo_console.application.cleanup_security_records import (
    CleanupSecurityRecordsCommand,
    CleanupSecurityRecordsResult,
)
from muxivo_console.infrastructure.security_cleanup_worker import (
    PeriodicSecurityCleanupWorker,
    PeriodicSecurityCleanupWorkerSettings,
)


class Cleanup:
    def __init__(self) -> None:
        self.commands: list[CleanupSecurityRecordsCommand] = []

    async def execute(
        self, command: CleanupSecurityRecordsCommand
    ) -> CleanupSecurityRecordsResult:
        self.commands.append(command)
        return CleanupSecurityRecordsResult(
            deleted_sessions=2,
            deleted_password_recovery_transactions=1,
        )


@pytest.mark.asyncio
async def test_security_cleanup_worker_run_once_delegates_retention_policy() -> None:
    cleanup = Cleanup()
    worker = PeriodicSecurityCleanupWorker(
        cleanup=cleanup,
        settings=PeriodicSecurityCleanupWorkerSettings(
            interval_seconds=60,
            initial_delay_seconds=0,
            session_retention_days=45,
            password_recovery_retention_hours=48,
        ),
    )

    await worker.run_once()

    assert cleanup.commands == [
        CleanupSecurityRecordsCommand(
            session_retention=timedelta(days=45),
            password_recovery_retention=timedelta(hours=48),
        )
    ]


@pytest.mark.asyncio
async def test_security_cleanup_worker_start_and_stop_without_waiting_for_interval() -> None:
    cleanup = Cleanup()
    worker = PeriodicSecurityCleanupWorker(
        cleanup=cleanup,
        settings=PeriodicSecurityCleanupWorkerSettings(
            interval_seconds=3600,
            initial_delay_seconds=300,
        ),
    )

    await worker.start()
    await asyncio.sleep(0)
    await worker.stop()

    assert cleanup.commands == []


def test_security_cleanup_worker_settings_validate_runtime_values() -> None:
    with pytest.raises(ValueError, match="interval"):
        PeriodicSecurityCleanupWorkerSettings(interval_seconds=0)
    with pytest.raises(ValueError, match="initial delay"):
        PeriodicSecurityCleanupWorkerSettings(initial_delay_seconds=-1)
    with pytest.raises(ValueError, match="session retention"):
        PeriodicSecurityCleanupWorkerSettings(session_retention_days=0)
    with pytest.raises(ValueError, match="password recovery retention"):
        PeriodicSecurityCleanupWorkerSettings(password_recovery_retention_hours=0)
