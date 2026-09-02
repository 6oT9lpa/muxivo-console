"""Command for creating an opaque browser session."""

from dataclasses import dataclass, field
from uuid import UUID

from muxivo_console.domain.sessions import SessionAssuranceLevel


@dataclass(frozen=True, slots=True)
class CreateBrowserSessionCommand:
    """Carry only the authenticated identity and safe client fingerprint inputs."""

    user_id: UUID
    correlation_id: UUID
    assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.PASSWORD
    client_ip: str | None = field(default=None, repr=False)
    user_agent: str | None = field(default=None, repr=False)
