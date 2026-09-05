"""Errors for the verified platform connection flow."""


class PlatformConnectionConnectRejectedError(PermissionError):
    """Safe failure for denied, unverified, or conflicting connection attempts."""
