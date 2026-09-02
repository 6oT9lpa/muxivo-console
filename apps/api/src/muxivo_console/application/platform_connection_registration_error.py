"""Errors for platform connection registration."""


class PlatformConnectionRegistrationRejectedError(PermissionError):
    """Safe failure for denied, unverified, or conflicting registrations."""
