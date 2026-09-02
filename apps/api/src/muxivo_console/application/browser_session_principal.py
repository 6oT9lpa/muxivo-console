"""Authenticated browser-session principal exposed to application use cases."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from muxivo_console.domain.sessions import SessionAssuranceLevel


@dataclass(frozen=True, slots=True)
class BrowserSessionPrincipal:
    """Identify the authenticated user and the assurance of its session."""

    user_id: UUID
    session_id: UUID
    assurance_level: SessionAssuranceLevel
    authenticated_at: datetime | None = None
