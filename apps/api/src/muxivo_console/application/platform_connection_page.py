"""Cursor-paginated non-secret platform connection response."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.connections import PlatformConnection


@dataclass(frozen=True, slots=True)
class PlatformConnectionPage:
    """Expose connection records and an opaque cursor for the next page."""

    items: tuple[PlatformConnection, ...]
    next_cursor: UUID | None
