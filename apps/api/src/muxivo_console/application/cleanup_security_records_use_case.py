"""Delete expired authentication security records after retention windows."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.cleanup_security_records_command import (
    CleanupSecurityRecordsCommand,
)
from muxivo_console.application.cleanup_security_records_result import CleanupSecurityRecordsResult
from muxivo_console.application.ports import Clock, SecurityRecordCleaner

logger = logging.getLogger("muxivo_console.application.cleanup_security_records")


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
                "deleted_password_recovery_transactions": deleted_password_recovery_transactions,
            },
        )
        return CleanupSecurityRecordsResult(
            deleted_sessions=deleted_sessions,
            deleted_password_recovery_transactions=deleted_password_recovery_transactions,
        )
