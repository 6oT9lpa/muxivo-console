"""Errors for authenticated login identity management."""


class LoginIdentityManagementRejectedError(PermissionError):
    """Safe failure for denied account identity management operations."""
