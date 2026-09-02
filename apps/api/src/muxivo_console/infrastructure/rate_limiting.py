"""Fixed-window rate limiting for abuse-prone Console browser flows."""

import asyncio
import hashlib
import logging
import ssl
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

from muxivo_console.application.ports import RateLimitDecision

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("Rate limit must allow at least one request.")
        if self.window_seconds < 1:
            raise ValueError("Rate limit window must be positive.")


@dataclass(slots=True)
class _RateLimitBucket:
    count: int
    reset_at: float


DEFAULT_AUTH_RATE_LIMIT_RULES: Mapping[str, RateLimitRule] = {
    "auth.registration": RateLimitRule(limit=5, window_seconds=60),
    "auth.login": RateLimitRule(limit=10, window_seconds=60),
    "auth.oauth.start": RateLimitRule(limit=10, window_seconds=60),
    "auth.oauth.callback": RateLimitRule(limit=20, window_seconds=60),
    "auth.reauthentication": RateLimitRule(limit=10, window_seconds=60),
    "auth.password_recovery.request": RateLimitRule(limit=5, window_seconds=60),
    "auth.password_recovery.complete": RateLimitRule(limit=10, window_seconds=60),
}


class InMemoryFixedWindowRateLimiter:
    """Simple process-local limiter; replace with Redis for multi-instance production."""

    def __init__(self, rules: Mapping[str, RateLimitRule]) -> None:
        self._rules = dict(rules)
        self._buckets: dict[tuple[str, str], _RateLimitBucket] = {}

    async def check(self, *, scope: str, key: str) -> RateLimitDecision:
        rule = self._rules.get(scope)
        if rule is None:
            logger.info("rate_limit.skipped", extra={"scope": scope, "reason": "missing_rule"})
            return RateLimitDecision(allowed=True)
        now = monotonic()
        bucket_key = (scope, key)
        bucket = self._buckets.get(bucket_key)
        if bucket is None or now >= bucket.reset_at:
            self._buckets[bucket_key] = _RateLimitBucket(
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


class RedisRateLimitUnavailableError(ConnectionError):
    """Raised when the shared Redis rate-limit backend cannot be reached safely."""


class RedisFixedWindowCounter:
    """Minimal Redis RESP client for atomic fixed-window counters."""

    _SCRIPT = (
        "local current = redis.call('INCR', KEYS[1]); "
        "if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
        "local ttl = redis.call('TTL', KEYS[1]); "
        "return {current, ttl};"
    )

    def __init__(self, redis_url: str, *, timeout_seconds: float = 2.0) -> None:
        parsed = urlparse(redis_url)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("Redis rate-limit URL must use redis:// or rediss://.")
        self._host = parsed.hostname
        self._port = parsed.port or 6379
        self._db = int(parsed.path.lstrip("/") or "0")
        self._username = parsed.username
        self._password = parsed.password
        self._ssl_context = ssl.create_default_context() if parsed.scheme == "rediss" else None
        self._timeout_seconds = timeout_seconds

    async def increment_windowed(self, *, key: str, window_seconds: int) -> tuple[int, int]:
        commands: list[tuple[str, ...]] = []
        if self._password is not None:
            if self._username is not None:
                commands.append(("AUTH", self._username, self._password))
            else:
                commands.append(("AUTH", self._password))
        if self._db:
            commands.append(("SELECT", str(self._db)))
        commands.append(("EVAL", self._SCRIPT, "1", key, str(window_seconds)))
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._host,
                    self._port,
                    ssl=self._ssl_context,
                ),
                timeout=self._timeout_seconds,
            )
            try:
                response = None
                for command in commands:
                    writer.write(_encode_redis_command(command))
                    await asyncio.wait_for(writer.drain(), timeout=self._timeout_seconds)
                    response = await asyncio.wait_for(
                        _read_redis_value(reader), timeout=self._timeout_seconds
                    )
            finally:
                writer.close()
                await writer.wait_closed()
        except (OSError, TimeoutError, ValueError) as error:
            raise RedisRateLimitUnavailableError("Redis rate limit backend unavailable.") from error
        if (
            not isinstance(response, list)
            or len(response) != 2
            or not all(isinstance(value, int) for value in response)
        ):
            raise RedisRateLimitUnavailableError("Redis rate limit backend returned invalid data.")
        return response[0], max(1, response[1])


class RedisFixedWindowRateLimiter:
    """Shared Redis-backed limiter suitable for multi-instance production."""

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


def _encode_redis_command(parts: Sequence[str]) -> bytes:
    encoded = [f"*{len(parts)}\r\n".encode("ascii")]
    for part in parts:
        value = part.encode("utf-8")
        encoded.append(f"${len(value)}\r\n".encode("ascii"))
        encoded.append(value + b"\r\n")
    return b"".join(encoded)


async def _read_redis_value(reader: asyncio.StreamReader):
    marker = await reader.readexactly(1)
    if marker == b"+":
        return (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
    if marker == b"-":
        message = (await reader.readline()).rstrip(b"\r\n").decode("utf-8")
        raise RedisRateLimitUnavailableError(message)
    if marker == b":":
        return int((await reader.readline()).rstrip(b"\r\n"))
    if marker == b"$":
        length = int((await reader.readline()).rstrip(b"\r\n"))
        if length < 0:
            return None
        payload = await reader.readexactly(length)
        await reader.readexactly(2)
        return payload.decode("utf-8")
    if marker == b"*":
        length = int((await reader.readline()).rstrip(b"\r\n"))
        if length < 0:
            return None
        return [await _read_redis_value(reader) for _ in range(length)]
    raise RedisRateLimitUnavailableError("Unsupported Redis response.")
