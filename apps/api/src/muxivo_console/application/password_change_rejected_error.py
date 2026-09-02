"""Public error for password-change failures."""


class PasswordChangeRejectedError(PermissionError):
    """Publicly safe password-change failure."""
