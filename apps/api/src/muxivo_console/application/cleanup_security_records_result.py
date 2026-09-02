"""Result of security-record retention cleanup."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CleanupSecurityRecordsResult:
    """Report the number of removed records by security-record type."""

    deleted_sessions: int
    deleted_password_recovery_transactions: int
