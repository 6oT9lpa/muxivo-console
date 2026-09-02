"""Errors for organization invitation operations."""


class OrganizationInvitationRejectedError(PermissionError):
    """Safe failure for unauthorized or conflicting invitation operations."""
