"""Retention cleanup for expired authentication security records."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from muxivo_console.application.ports import Clock, SecurityRecordCleaner

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CleanupSecurityRecordsCommand:
    session_retention: timedelta = timedelta(days=30)
    password_recovery_retention: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if self.session_retention <= timedelta(0):
            raise ValueError("Session retention must be positive.")
        if self.password_recovery_retention <= timedelta(0):
            raise ValueError("Password recovery retention must be positive.")


@dataclass(frozen=True, slots=True)
class CleanupSecurityRecordsResult:
    deleted_sessions: int
    deleted_password_recovery_transactions: int


@dataclass(slots=True)
class CleanupSecurityRecords:
    """Delete security records only after the configured retention window elapsed."""

    clock: Clock
    cleaner: SecurityRecordCleaner

    async def execute(self, command: CleanupSecurityRecordsCommand) -> CleanupSecurityRecordsResult:
        now = self.clock.now()
        session_cutoff = now - command.session_retention
        password_recovery_cutoff = now - command.password_recovery_retention
        logger.info(
            "security.cleanup.started",
            extra={
                "session_cutoff": session_cutoff.isoformat(),
                "password_recovery_cutoff": password_recovery_cutoff.isoformat(),
            },
        )
        deleted_sessions = await self.cleaner.delete_expired_or_revoked_sessions(
            before=session_cutoff
        )
        deleted_password_recovery_transactions = (
            await self.cleaner.delete_consumed_or_expired_password_recovery_transactions(
                before=password_recovery_cutoff
            )
        )
        logger.info(
            "security.cleanup.completed",
            extra={
                "deleted_sessions": deleted_sessions,
                "deleted_password_recovery_transactions": (deleted_password_recovery_transactions),
            },
        )
        return CleanupSecurityRecordsResult(
            deleted_sessions=deleted_sessions,
            deleted_password_recovery_transactions=deleted_password_recovery_transactions,
        )
