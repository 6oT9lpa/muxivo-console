"""Periodic security cleanup worker settings."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PeriodicSecurityCleanupWorkerSettings:
    """Validated schedule and retention settings for security cleanup ticks."""

    interval_seconds: float = 86_400.0
    initial_delay_seconds: float = 60.0
    session_retention_days: int = 30
    password_recovery_retention_hours: int = 24

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("Security cleanup interval must be positive.")
        if self.initial_delay_seconds < 0:
            raise ValueError("Security cleanup initial delay must not be negative.")
        if self.session_retention_days <= 0:
            raise ValueError("Security cleanup session retention must be positive.")
        if self.password_recovery_retention_hours <= 0:
            raise ValueError("Security cleanup password recovery retention must be positive.")
