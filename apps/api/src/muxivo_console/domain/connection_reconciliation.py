"""Domain DTOs for periodic platform connection reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.connections import ConnectionStatus


class ConnectionReconciliationReason(StrEnum):
    HEALTHY = "healthy"
    PREFLIGHT_FAILED = "preflight_failed"
    TOKEN_EXPIRED = "token_expired"
    SCOPES_MISSING = "scopes_missing"
    PLATFORM_UNREACHABLE = "platform_unreachable"
    RESOURCE_REMOVED = "resource_removed"


_ALLOWED_TARGET_STATUSES: dict[ConnectionReconciliationReason, frozenset[ConnectionStatus]] = {
    # PENDING/DEGRADED are accepted here for a deliberate no-op decision when
    # a platform-specific probe receives a connection owned by another platform.
    ConnectionReconciliationReason.HEALTHY: frozenset(
        {ConnectionStatus.PENDING, ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}
    ),
    ConnectionReconciliationReason.PREFLIGHT_FAILED: frozenset(
        {ConnectionStatus.PENDING, ConnectionStatus.DEGRADED}
    ),
    ConnectionReconciliationReason.TOKEN_EXPIRED: frozenset({ConnectionStatus.REAUTH_REQUIRED}),
    ConnectionReconciliationReason.SCOPES_MISSING: frozenset({ConnectionStatus.REAUTH_REQUIRED}),
    ConnectionReconciliationReason.PLATFORM_UNREACHABLE: frozenset({ConnectionStatus.DEGRADED}),
    ConnectionReconciliationReason.RESOURCE_REMOVED: frozenset({ConnectionStatus.DISCONNECTED}),
}


@dataclass(frozen=True, slots=True)
class ConnectionReconciliationDecision:
    target_status: ConnectionStatus
    reason: ConnectionReconciliationReason

    def __post_init__(self) -> None:
        if not isinstance(self.target_status, ConnectionStatus):
            raise ValueError("Connection reconciliation target status is invalid.")
        if not isinstance(self.reason, ConnectionReconciliationReason):
            raise ValueError("Connection reconciliation reason is invalid.")
        if self.target_status not in _ALLOWED_TARGET_STATUSES[self.reason]:
            raise ValueError("Connection reconciliation reason does not match target status.")
