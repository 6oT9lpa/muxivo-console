"""Public error for first-party registration failures."""


class RegistrationRejectedError(ValueError):
    """Publicly safe registration failure that never reveals account existence."""
