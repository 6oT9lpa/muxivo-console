"""Public error for first-party authentication failures."""


class AuthenticationRejectedError(PermissionError):
    """Publicly safe failure that never reveals account existence."""
