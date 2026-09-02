"""Background service presentation protocol."""

from typing import Protocol


class BackgroundService(Protocol):
    """Lifecycle contract for services managed by the FastAPI application."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...
