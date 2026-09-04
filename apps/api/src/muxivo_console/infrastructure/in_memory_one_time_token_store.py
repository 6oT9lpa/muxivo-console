"""Small process-local token store used only by development composition/tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class InMemoryOneTimeTokenStore:
    """Implement the token port without persisting secrets outside the process."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[str, datetime]] = {}

    async def put(self, *, key: str, value: str, ttl_seconds: int) -> bool:
        self._purge_expired()
        if key in self._values:
            return False
        self._values[key] = (value, _expires_at(ttl_seconds))
        return True

    async def get(self, *, key: str) -> str | None:
        self._purge_expired()
        stored = self._values.get(key)
        return stored[0] if stored is not None else None

    async def replace(self, *, key: str, value: str, ttl_seconds: int) -> bool:
        self._purge_expired()
        if key not in self._values:
            return False
        self._values[key] = (value, _expires_at(ttl_seconds))
        return True

    async def consume(self, *, key: str, value: str) -> bool:
        self._purge_expired()
        stored = self._values.get(key)
        if stored is None or stored[0] != value:
            return False
        del self._values[key]
        return True

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        self._values = {key: stored for key, stored in self._values.items() if stored[1] > now}


def _expires_at(ttl_seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=max(1, ttl_seconds))
