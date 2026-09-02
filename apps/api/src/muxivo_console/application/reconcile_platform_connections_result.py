"""Result of a platform-connection reconciliation pass."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconcilePlatformConnectionsResult:
    """Report inspected, changed and skipped connection records."""

    inspected: int
    changed: int
    skipped: int
