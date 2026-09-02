"""Periodic platform reconciliation worker settings."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PeriodicReconciliationWorkerSettings:
    """Validated schedule and batch settings for reconciliation ticks."""

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
