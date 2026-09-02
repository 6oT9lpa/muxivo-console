"""Errors for browser session creation."""


class SessionCreationRejectedError(PermissionError):
    """Raised when an inactive user attempts to create a Console browser session."""
