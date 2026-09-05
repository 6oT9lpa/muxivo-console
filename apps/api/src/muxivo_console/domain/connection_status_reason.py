"""Stable, browser-safe reasons for platform connection state."""

from enum import StrEnum


class ConnectionStatusReason(StrEnum):
    """Explain why a Console-owned connection currently has its state."""

    INITIAL_PENDING = "initial_pending"
    HEALTHY = "healthy"
    PREFLIGHT_FAILED = "preflight_failed"
    TOKEN_EXPIRED = "token_expired"
    SCOPES_MISSING = "scopes_missing"
    PLATFORM_UNREACHABLE = "platform_unreachable"
    RESOURCE_REMOVED = "resource_removed"
    REAUTHORIZED = "reauthorized"
    REVOKED = "revoked"
    DISCONNECTED = "disconnected"
