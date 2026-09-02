"""Errors for starting provider OAuth login."""


class OAuthLoginStartRejectedError(PermissionError):
    """Publicly safe failure for OAuth login initialization."""
