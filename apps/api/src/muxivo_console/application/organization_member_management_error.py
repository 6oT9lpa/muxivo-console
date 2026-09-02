"""Errors shared by organization member management use cases."""


class OrganizationMemberManagementRejectedError(PermissionError):
    """Raised when a membership operation must fail closed."""
