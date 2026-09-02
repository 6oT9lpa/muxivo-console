"""Process-local fixed-window rate limiter."""

import logging
from collections.abc import Mapping
from time import monotonic

from muxivo_console.application.ports import RateLimitDecision
from muxivo_console.infrastructure.rate_limit_bucket import RateLimitBucket
from muxivo_console.infrastructure.rate_limit_rule import RateLimitRule

logger = logging.getLogger("muxivo_console.infrastructure.rate_limiting")


class InMemoryFixedWindowRateLimiter:
    """Provide a development-only process-local fixed-window limiter."""

    def __init__(self, rules: Mapping[str, RateLimitRule]) -> None:
        self._rules = dict(rules)
        self._buckets: dict[tuple[str, str], RateLimitBucket] = {}

    async def check(self, *, scope: str, key: str) -> RateLimitDecision:
        rule = self._rules.get(scope)
        if rule is None:
            logger.info("rate_limit.skipped", extra={"scope": scope, "reason": "missing_rule"})
            return RateLimitDecision(allowed=True)
        now = monotonic()
        bucket_key = (scope, key)
        bucket = self._buckets.get(bucket_key)
        if bucket is None or now >= bucket.reset_at:
            self._buckets[bucket_key] = RateLimitBucket(
                count=1,
                reset_at=now + rule.window_seconds,
            )
            logger.info("rate_limit.allowed", extra={"scope": scope, "remaining": rule.limit - 1})
            return RateLimitDecision(allowed=True)
        if bucket.count >= rule.limit:
            retry_after = max(1, int(bucket.reset_at - now))
            logger.warning(
                "rate_limit.denied",
                extra={"scope": scope, "retry_after_seconds": retry_after},
            )
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=retry_after,
            )
        bucket.count += 1
        logger.info(
            "rate_limit.allowed",
            extra={"scope": scope, "remaining": rule.limit - bucket.count},
        )
        return RateLimitDecision(allowed=True)
