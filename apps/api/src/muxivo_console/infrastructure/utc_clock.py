"""UTC clock adapter."""

from datetime import UTC, datetime


class UtcClock:
    """Provide timezone-aware UTC timestamps to application use cases."""

    def now(self) -> datetime:
        return datetime.now(UTC)
