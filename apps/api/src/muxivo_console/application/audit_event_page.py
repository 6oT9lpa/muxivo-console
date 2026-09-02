"""Cursor-paginated organization audit response."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.audit import AuditLogEntry


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    """Expose audit entries and the opaque cursor for the next page."""

    items: tuple[AuditLogEntry, ...]
    next_cursor: UUID | None
