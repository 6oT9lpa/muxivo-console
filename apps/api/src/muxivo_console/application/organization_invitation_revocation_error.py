"""Errors for revoking organization invitations."""


class OrganizationInvitationRevocationRejectedError(PermissionError):
    """Safe failure for missing, expired or unauthorized invitation revocation."""
