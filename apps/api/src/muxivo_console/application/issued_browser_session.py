"""One-time browser session credentials returned by the session creator."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from muxivo_console.domain.sessions import SessionAssuranceLevel


@dataclass(frozen=True, slots=True)
class IssuedBrowserSession:
    """Raw browser credentials are excluded from repr/logging and returned once only."""

    id: UUID
    raw_token: str = field(repr=False)
    raw_csrf_token: str = field(repr=False)
    expires_at: datetime
    assurance_level: SessionAssuranceLevel
