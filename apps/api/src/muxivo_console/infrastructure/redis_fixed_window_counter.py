"""Minimal Redis RESP fixed-window counter adapter."""

import asyncio
import ssl
from collections.abc import Sequence
from urllib.parse import urlparse

from muxivo_console.infrastructure.redis_rate_limit_unavailable_error import (
    RedisRateLimitUnavailableError,
)


class RedisFixedWindowCounter:
    """Increment a Redis counter atomically using a bounded network operation."""

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
