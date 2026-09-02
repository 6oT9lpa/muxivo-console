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


@dataclass(frozen=True, slots=True)
class ConnectionReconciliationDecision:
    target_status: ConnectionStatus
    reason: ConnectionReconciliationReason
