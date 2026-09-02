"""Public error for organization creation failures."""


class OrganizationCreationRejectedError(PermissionError):
    """Raised when the current user may not create an organization."""
