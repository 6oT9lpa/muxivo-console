"""Errors for linking verified provider identities."""


class IdentityLinkRejectedError(PermissionError):
    """Publicly safe failure for inactive, invalid, or already-linked identities."""
