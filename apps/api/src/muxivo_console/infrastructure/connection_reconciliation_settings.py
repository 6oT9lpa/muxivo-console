"""Platform connection reconciliation configuration value object."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConnectionReconciliationSettings:
    """Validated settings for the periodic connection reconciliation worker."""

    enabled: bool
    system_actor_id: UUID
    interval_seconds: float = 300.0
    initial_delay_seconds: float = 10.0
    batch_limit: int = 100
