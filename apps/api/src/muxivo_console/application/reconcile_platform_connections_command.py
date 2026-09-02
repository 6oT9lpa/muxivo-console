"""Command for a bounded platform-connection reconciliation pass."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReconcilePlatformConnectionsCommand:
    """Identify the system actor and maximum number of records to inspect."""

    system_actor_id: UUID
    correlation_id: UUID
    limit: int = 100
