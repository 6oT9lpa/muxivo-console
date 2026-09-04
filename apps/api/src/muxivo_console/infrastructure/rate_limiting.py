"""Compatibility facade for the Console rate-limit adapters."""

from collections.abc import Mapping

from muxivo_console.infrastructure.in_memory_fixed_window_rate_limiter import (
    InMemoryFixedWindowRateLimiter,
)
from muxivo_console.infrastructure.rate_limit_rule import RateLimitRule
from muxivo_console.infrastructure.redis_fixed_window_counter import RedisFixedWindowCounter
from muxivo_console.infrastructure.redis_fixed_window_rate_limiter import (
    RedisFixedWindowRateLimiter,
)
from muxivo_console.infrastructure.redis_rate_limit_unavailable_error import (
    RedisRateLimitUnavailableError,
)

DEFAULT_AUTH_RATE_LIMIT_RULES: Mapping[str, RateLimitRule] = {
    "auth.registration": RateLimitRule(limit=5, window_seconds=60),
    "auth.registration.verification": RateLimitRule(limit=10, window_seconds=60),
    "auth.registration.resend": RateLimitRule(limit=3, window_seconds=300),
    "auth.login": RateLimitRule(limit=10, window_seconds=60),
    "auth.oauth.start": RateLimitRule(limit=10, window_seconds=60),
    "auth.oauth.callback": RateLimitRule(limit=20, window_seconds=60),
    "auth.reauthentication": RateLimitRule(limit=10, window_seconds=60),
    "auth.password_recovery.request": RateLimitRule(limit=5, window_seconds=60),
    "auth.password_recovery.complete": RateLimitRule(limit=10, window_seconds=60),
    "auth.invitation.accept": RateLimitRule(limit=10, window_seconds=60),
    "organization.invitation.create": RateLimitRule(limit=20, window_seconds=60),
}

__all__ = [
    "DEFAULT_AUTH_RATE_LIMIT_RULES",
    "InMemoryFixedWindowRateLimiter",
    "RateLimitRule",
    "RedisFixedWindowCounter",
    "RedisFixedWindowRateLimiter",
    "RedisRateLimitUnavailableError",
]
