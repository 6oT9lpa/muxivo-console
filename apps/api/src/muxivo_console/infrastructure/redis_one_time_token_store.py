"""Minimal Redis RESP adapter for encrypted pending-auth values."""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import Sequence
from urllib.parse import urlparse

from muxivo_console.infrastructure.redis_one_time_token_store_unavailable_error import (
    RedisOneTimeTokenStoreUnavailableError,
)


class RedisOneTimeTokenStore:
    """Store short-lived values and consume them with compare-and-delete Lua."""

    _CONSUME_SCRIPT = (
        "if redis.call('GET', KEYS[1]) == ARGV[1] then "
        "return redis.call('DEL', KEYS[1]); else return 0; end;"
    )

    def __init__(self, redis_url: str, *, timeout_seconds: float = 2.0) -> None:
        parsed = urlparse(redis_url)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("Redis token store URL must use redis:// or rediss://.")
        self._host = parsed.hostname
        self._port = parsed.port or 6379
        self._db = int(parsed.path.lstrip("/") or "0")
        self._username = parsed.username
        self._password = parsed.password
        self._ssl_context = ssl.create_default_context() if parsed.scheme == "rediss" else None
        self._timeout_seconds = timeout_seconds

    async def put(self, *, key: str, value: str, ttl_seconds: int) -> bool:
        response = await self._command("SET", key, value, "EX", str(max(1, ttl_seconds)), "NX")
        return response == "OK"

    async def get(self, *, key: str) -> str | None:
        response = await self._command("GET", key)
        if response is None or isinstance(response, str):
            return response
        raise RedisOneTimeTokenStoreUnavailableError("Redis token store returned invalid data.")

    async def replace(self, *, key: str, value: str, ttl_seconds: int) -> bool:
        response = await self._command("SET", key, value, "EX", str(max(1, ttl_seconds)))
        return response == "OK"

    async def consume(self, *, key: str, value: str) -> bool:
        response = await self._command("EVAL", self._CONSUME_SCRIPT, "1", key, value)
        return response == 1

    async def _command(self, *parts: str):
        commands: list[tuple[str, ...]] = []
        if self._password is not None:
            if self._username is not None:
                commands.append(("AUTH", self._username, self._password))
            else:
                commands.append(("AUTH", self._password))
        if self._db:
            commands.append(("SELECT", str(self._db)))
        commands.append(tuple(parts))
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
                return response
            finally:
                writer.close()
                await writer.wait_closed()
        except (asyncio.IncompleteReadError, OSError, TimeoutError, ValueError) as error:
            raise RedisOneTimeTokenStoreUnavailableError(
                "Redis token store unavailable."
            ) from error


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
        raise RedisOneTimeTokenStoreUnavailableError(message)
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
    raise RedisOneTimeTokenStoreUnavailableError("Unsupported Redis response.")
