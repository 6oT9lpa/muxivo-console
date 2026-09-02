"""Shared Redis-backed fixed-window rate limiter."""

import hashlib
import logging
from collections.abc import Mapping

from muxivo_console.application.ports import RateLimitDecision
from muxivo_console.infrastructure.rate_limit_rule import RateLimitRule
from muxivo_console.infrastructure.redis_fixed_window_counter import RedisFixedWindowCounter
from muxivo_console.infrastructure.redis_rate_limit_unavailable_error import (
    RedisRateLimitUnavailableError,
)

logger = logging.getLogger("muxivo_console.infrastructure.rate_limiting")


class RedisFixedWindowRateLimiter:
    """Provide a shared Redis-backed limiter suitable for multiple API instances."""

    def __init__(
        self,
        *,
        rules: Mapping[str, RateLimitRule],
        counter: RedisFixedWindowCounter,
        key_prefix: str = "muxivo-console:rate-limit",
    ) -> None:
        self._rules = dict(rules)
        self._counter = counter
        self._key_prefix = key_prefix.rstrip(":")

    async def check(self, *, scope: str, key: str) -> RateLimitDecision:
        rule = self._rules.get(scope)
        if rule is None:
            logger.info("rate_limit.skipped", extra={"scope": scope, "reason": "missing_rule"})
            return RateLimitDecision(allowed=True)
        redis_key = self._redis_key(scope=scope, key=key)
        try:
            count, ttl = await self._counter.increment_windowed(
                key=redis_key,
                window_seconds=rule.window_seconds,
            )
        except RedisRateLimitUnavailableError:
            logger.error("rate_limit.backend_unavailable", extra={"scope": scope})
            return RateLimitDecision(allowed=False, retry_after_seconds=rule.window_seconds)
        if count > rule.limit:
            logger.warning(
                "rate_limit.denied",
                extra={"scope": scope, "retry_after_seconds": ttl},
            )
            return RateLimitDecision(allowed=False, retry_after_seconds=ttl)
        logger.info("rate_limit.allowed", extra={"scope": scope, "remaining": rule.limit - count})
        return RateLimitDecision(allowed=True)

    def _redis_key(self, *, scope: str, key: str) -> str:
        digest = hashlib.sha256(f"{scope}:{key}".encode()).hexdigest()
        return f"{self._key_prefix}:{scope}:{digest}"
