"""Errors for platform connection lifecycle operations."""


class PlatformConnectionLifecycleRejectedError(PermissionError):
    """Safe failure for unauthorized, missing, or invalid lifecycle transitions."""
