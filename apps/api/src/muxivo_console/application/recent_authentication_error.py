"""Errors for recent-authentication policy checks."""


class RecentAuthenticationRequiredError(PermissionError):
    """Raised when the caller must reauthenticate before a sensitive command."""
