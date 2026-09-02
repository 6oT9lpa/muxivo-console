"""Redis rate-limit backend failure."""


class RedisRateLimitUnavailableError(ConnectionError):
    """Raised when the shared Redis rate-limit backend is unavailable or invalid."""
