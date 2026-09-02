"""Security-record cleanup configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecurityCleanupSettings:
    """Validated retention and scheduling settings for security cleanup."""

    enabled: bool
    interval_seconds: float = 86_400.0
    initial_delay_seconds: float = 60.0
    session_retention_days: int = 30
    password_recovery_retention_hours: int = 24
