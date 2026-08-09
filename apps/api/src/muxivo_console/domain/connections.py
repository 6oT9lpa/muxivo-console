"""Lifecycle rules for Organization-owned platform adapter connections."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from muxivo_console.domain.activity import Platform


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DEGRADED = "degraded"
    REAUTH_REQUIRED = "reauth_required"
    DISCONNECTED = "disconnected"


_ALLOWED_TRANSITIONS: dict[ConnectionStatus, frozenset[ConnectionStatus]] = {
    ConnectionStatus.PENDING: frozenset({ConnectionStatus.ACTIVE, ConnectionStatus.DISCONNECTED}),
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

    def __post_init__(self) -> None:
        if not self.external_resource_id.strip() or len(self.external_resource_id) > 255:
            raise ValueError("External resource identifier must contain 1 to 255 characters.")

    def transition_to(self, target: ConnectionStatus) -> "PlatformConnection":
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Cannot transition connection from {self.status} to {target}.")
        return PlatformConnection(
            id=self.id,
            organization_id=self.organization_id,
            platform=self.platform,
            external_resource_id=self.external_resource_id,
            status=target,
        )
