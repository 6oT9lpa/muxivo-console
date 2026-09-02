"""Server-side browser session entities; raw bearer values never belong here."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SessionAssuranceLevel(StrEnum):
    PASSWORD = "password"
    RECENT_AUTHENTICATION = "recent_authentication"


@dataclass(frozen=True, slots=True)
class AuthSession:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    assurance_level: SessionAssuranceLevel
    revoked_at: datetime | None = None
    authenticated_at: datetime | None = None
    last_seen_at: datetime | None = None
    ip_hash: str | None = None
    user_agent_hash: str | None = None

    def __post_init__(self) -> None:
        if len(self.token_hash) != 64:
            raise ValueError("Session token hash must be a SHA-256-sized hex digest.")
        if self.expires_at.tzinfo is None:
            raise ValueError("Session expiry must be timezone-aware.")
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            raise ValueError("Session revocation time must be timezone-aware.")
        if self.authenticated_at is not None and self.authenticated_at.tzinfo is None:
            raise ValueError("Session authentication time must be timezone-aware.")
        if self.last_seen_at is not None and self.last_seen_at.tzinfo is None:
            raise ValueError("Session last-seen time must be timezone-aware.")
        if self.ip_hash is not None and len(self.ip_hash) != 64:
            raise ValueError("Session IP hash must be a SHA-256-sized hex digest.")
        if self.user_agent_hash is not None and len(self.user_agent_hash) != 64:
            raise ValueError("Session user-agent hash must be a SHA-256-sized hex digest.")

    def is_active_at(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("Session checks require a timezone-aware instant.")
        return self.revoked_at is None and instant < self.expires_at
