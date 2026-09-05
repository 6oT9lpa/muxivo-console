"""Lifecycle rules for Organization-owned platform adapter connections."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DEGRADED = "degraded"
    REAUTH_REQUIRED = "reauth_required"
    DISCONNECTED = "disconnected"


_ALLOWED_TRANSITIONS: dict[ConnectionStatus, frozenset[ConnectionStatus]] = {
    ConnectionStatus.PENDING: frozenset(
        {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DEGRADED,
            ConnectionStatus.REAUTH_REQUIRED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.ACTIVE: frozenset(
        {
            ConnectionStatus.DEGRADED,
            ConnectionStatus.REAUTH_REQUIRED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.DEGRADED: frozenset(
        {
            ConnectionStatus.ACTIVE,
            ConnectionStatus.REAUTH_REQUIRED,
            ConnectionStatus.DISCONNECTED,
        }
    ),
    ConnectionStatus.REAUTH_REQUIRED: frozenset(
        {ConnectionStatus.ACTIVE, ConnectionStatus.DISCONNECTED}
    ),
    ConnectionStatus.DISCONNECTED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class PlatformConnection:
    """Non-secret ownership record for one platform resource in an Organization."""

    id: UUID
    organization_id: UUID
    platform: Platform
    external_resource_id: str
    status: ConnectionStatus
    status_reason: ConnectionStatusReason | None = None
    granted_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.external_resource_id.strip() or len(self.external_resource_id) > 255:
            raise ValueError("External resource identifier must contain 1 to 255 characters.")
        if self.status_reason is not None and not isinstance(
            self.status_reason, ConnectionStatusReason
        ):
            raise ValueError("Connection status reason is invalid.")
        if any(
            not capability.strip() or len(capability) > 128
            for capability in self.granted_capabilities
        ):
            raise ValueError("Connection capability keys must contain 1 to 128 characters.")
        if len(set(self.granted_capabilities)) != len(self.granted_capabilities):
            raise ValueError("Connection capability keys must be unique.")

    def transition_to(
        self,
        target: ConnectionStatus,
        *,
        reason: ConnectionStatusReason | None = None,
    ) -> "PlatformConnection":
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Cannot transition connection from {self.status} to {target}.")
        return PlatformConnection(
            id=self.id,
            organization_id=self.organization_id,
            platform=self.platform,
            external_resource_id=self.external_resource_id,
            status=target,
            status_reason=reason,
            granted_capabilities=self.granted_capabilities,
        )


@dataclass(frozen=True, slots=True)
class PlatformConnectionLifecycleIdempotencyResult:
    """Previously persisted result for one lifecycle command retry key."""

    organization_id: UUID
    connection_id: UUID
    action: str
    result_status: ConnectionStatus
    result_reason: ConnectionStatusReason | None = None

    def __post_init__(self) -> None:
        if not self.action.strip():
            raise ValueError("Lifecycle idempotency action must be non-empty.")
