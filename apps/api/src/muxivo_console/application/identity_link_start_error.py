"""Errors for starting an external identity link."""


class IdentityLinkStartRejectedError(PermissionError):
    """Safe public failure for an unusable OAuth link initiation."""
