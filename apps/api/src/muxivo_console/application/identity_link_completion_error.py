"""Errors for completing an external identity link."""


class IdentityLinkCompletionRejectedError(PermissionError):
    """Publicly safe OAuth callback failure without state/provider detail."""
