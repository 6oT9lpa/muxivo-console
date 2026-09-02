"""Shared application error for authorization failures."""


class AccessDeniedError(PermissionError):
    """Raised when a session actor cannot access an organization resource."""
