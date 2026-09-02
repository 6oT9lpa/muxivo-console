"""Fixed-window rate-limit rule value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """Describe the maximum requests permitted in one fixed window."""

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("Rate limit must allow at least one request.")
        if self.window_seconds < 1:
            raise ValueError("Rate limit window must be positive.")
