"""Errors for listing organization invitations."""


class OrganizationInvitationListingRejectedError(PermissionError):
    """Raised when an actor cannot inspect organization invitations."""
