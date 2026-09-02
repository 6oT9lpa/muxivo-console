"""One-time first-party password recovery transactions."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PasswordRecoveryTransaction:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        if len(self.token_hash) != 64:
            raise ValueError("Password recovery token hash must be SHA-256-sized.")
        if self.expires_at.tzinfo is None:
            raise ValueError("Password recovery expiry must be timezone-aware.")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise ValueError("Password recovery consumption time must be timezone-aware.")

    def is_active_at(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("Password recovery checks require a timezone-aware instant.")
        return self.consumed_at is None and instant < self.expires_at
