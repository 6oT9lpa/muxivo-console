"""Public error for organization-list failures."""


class OrganizationListRejectedError(PermissionError):
    """Raised when the current principal cannot list organizations."""
