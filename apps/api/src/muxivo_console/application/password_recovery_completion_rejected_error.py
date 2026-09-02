"""Public error for password-recovery completion failures."""


class PasswordRecoveryCompletionRejectedError(PermissionError):
    """Safe failure for invalid, expired or already consumed recovery tokens."""
