"""Redis failure raised by the pending-auth token adapter."""


class RedisOneTimeTokenStoreUnavailableError(ConnectionError):
    """The verification token backend is unavailable or returned invalid data."""
