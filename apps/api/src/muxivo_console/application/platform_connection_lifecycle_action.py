"""Supported platform connection lifecycle actions."""

from enum import StrEnum

from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus


class PlatformConnectionLifecycleAction(StrEnum):
    """Map a user action to its Console-owned lifecycle state and audit name."""

    REAUTHORIZE = "reauthorize"
    REVOKE = "revoke"
    DISCONNECT = "disconnect"

    @property
    def target_status(self) -> ConnectionStatus:
        if self is PlatformConnectionLifecycleAction.REAUTHORIZE:
            return ConnectionStatus.ACTIVE
        if self is PlatformConnectionLifecycleAction.REVOKE:
            return ConnectionStatus.REAUTH_REQUIRED
        return ConnectionStatus.DISCONNECTED

    @property
    def audit_action(self) -> str:
        return f"platform_connection.{self.value}"

    @property
    def status_reason(self) -> ConnectionStatusReason:
        if self is PlatformConnectionLifecycleAction.REAUTHORIZE:
            return ConnectionStatusReason.REAUTHORIZED
        if self is PlatformConnectionLifecycleAction.REVOKE:
            return ConnectionStatusReason.REVOKED
        return ConnectionStatusReason.DISCONNECTED
