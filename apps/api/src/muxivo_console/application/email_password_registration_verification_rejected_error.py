"""Generic public error for invalid or exhausted e-mail verification flows."""


class EmailPasswordRegistrationVerificationRejectedError(PermissionError):
    """Keep token expiry, replay and wrong-code reasons indistinguishable publicly."""
