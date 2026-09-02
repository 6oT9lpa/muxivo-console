"""Public error for unavailable platform health."""


class PlatformHealthUnavailableError(RuntimeError):
    """The organization has no connection that may safely expose platform health."""
