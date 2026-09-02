"""Rate-limit backend configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitSettings:
    """Validated rate-limit backend and optional Redis connection."""

    backend: str
    redis_url: str | None = None
