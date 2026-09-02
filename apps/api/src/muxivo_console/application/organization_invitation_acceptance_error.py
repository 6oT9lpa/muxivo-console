"""Errors for accepting organization invitations."""


class OrganizationInvitationAcceptanceRejectedError(PermissionError):
    """Safe failure for invalid, expired, consumed or mismatched invitations."""
