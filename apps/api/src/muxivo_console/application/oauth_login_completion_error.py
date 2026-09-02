"""Errors for completing provider OAuth login."""


class OAuthLoginCompletionRejectedError(PermissionError):
    """Publicly safe callback failure without account-enumeration detail."""
