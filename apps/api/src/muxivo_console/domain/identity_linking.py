"""Server-side OAuth authorization transactions for external identity linking."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class IdentityLinkTransaction:
    id: UUID
    user_id: UUID
    provider: LoginIdentityProvider
    state_hash: str
    code_verifier_ciphertext: bytes
    expires_at: datetime
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.provider is LoginIdentityProvider.EMAIL:
            raise ValueError("E-mail is not an external OAuth identity provider.")
        if len(self.state_hash) != 64:
            raise ValueError("OAuth state hash must be a SHA-256-sized hex digest.")
        if not self.code_verifier_ciphertext:
            raise ValueError("OAuth PKCE verifier ciphertext must not be empty.")
        if self.expires_at.tzinfo is None:
            raise ValueError("OAuth transaction expiry must be timezone-aware.")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise ValueError("OAuth transaction consumption must be timezone-aware.")

    def is_usable_at(self, instant: datetime) -> bool:
        if instant.tzinfo is None:
            raise ValueError("OAuth transaction checks require a timezone-aware instant.")
        return self.consumed_at is None and instant < self.expires_at
