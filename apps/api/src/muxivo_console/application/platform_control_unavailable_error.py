"""Public error for unavailable or invalid platform control data."""


class PlatformControlUnavailableError(RuntimeError):
    """Raised when an authorized platform Control API is unavailable or invalid."""
