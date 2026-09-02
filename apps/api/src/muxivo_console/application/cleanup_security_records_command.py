"""Command for security-record retention cleanup."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class CleanupSecurityRecordsCommand:
    """Define positive retention windows for security data."""

    session_retention: timedelta = timedelta(days=30)
    password_recovery_retention: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if self.session_retention <= timedelta(0):
            raise ValueError("Session retention must be positive.")
        if self.password_recovery_retention <= timedelta(0):
            raise ValueError("Password recovery retention must be positive.")
