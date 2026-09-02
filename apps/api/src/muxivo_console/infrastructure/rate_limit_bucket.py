"""Internal in-memory rate-limit bucket value object."""

from dataclasses import dataclass


@dataclass(slots=True)
class RateLimitBucket:
    """Track request count and monotonic reset time for one limiter key."""

    count: int
    reset_at: float
