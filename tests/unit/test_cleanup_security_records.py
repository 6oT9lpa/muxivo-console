from datetime import UTC, datetime, timedelta

import pytest
from muxivo_console.application.cleanup_security_records import (
    CleanupSecurityRecords,
    CleanupSecurityRecordsCommand,
)


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 22, 12, tzinfo=UTC)


class Cleaner:
    def __init__(self) -> None:
        self.session_cutoff: datetime | None = None
        self.password_recovery_cutoff: datetime | None = None

    async def delete_expired_or_revoked_sessions(self, *, before) -> int:
        self.session_cutoff = before
        return 7

    async def delete_consumed_or_expired_password_recovery_transactions(self, *, before) -> int:
        self.password_recovery_cutoff = before
        return 3


@pytest.mark.asyncio
async def test_cleanup_security_records_deletes_only_after_retention_cutoffs() -> None:
    cleaner = Cleaner()
    use_case = CleanupSecurityRecords(clock=Clock(), cleaner=cleaner)

    result = await use_case.execute(
        CleanupSecurityRecordsCommand(
            session_retention=timedelta(days=30),
            password_recovery_retention=timedelta(hours=24),
        )
    )

    assert result.deleted_sessions == 7
    assert result.deleted_password_recovery_transactions == 3
    assert cleaner.session_cutoff == datetime(2026, 7, 23, 12, tzinfo=UTC)
    assert cleaner.password_recovery_cutoff == datetime(2026, 8, 21, 12, tzinfo=UTC)


def test_cleanup_security_records_rejects_non_positive_retention() -> None:
    with pytest.raises(ValueError, match="Session retention"):
        CleanupSecurityRecordsCommand(session_retention=timedelta())

    with pytest.raises(ValueError, match="Password recovery retention"):
        CleanupSecurityRecordsCommand(password_recovery_retention=timedelta())
