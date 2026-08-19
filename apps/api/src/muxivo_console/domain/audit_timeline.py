"""Sanitized platform audit timeline suitable for a browser control plane."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformAuditTimelineEvent:
    event_type: str
    occurred_at: str

    def __post_init__(self) -> None:
        if not self.event_type.strip() or not self.occurred_at.strip():
            raise ValueError("Audit timeline events require a type and occurrence time.")


@dataclass(frozen=True, slots=True)
class PlatformAuditTimeline:
    """No actors, targets, message content, reasons or raw event metadata."""

    platform: Platform
    events: tuple[PlatformAuditTimelineEvent, ...]
    limit: int

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100 or len(self.events) > self.limit:
            raise ValueError("Audit timeline limit is invalid.")
