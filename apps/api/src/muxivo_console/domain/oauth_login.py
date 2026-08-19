"""One-time OAuth login transaction; separate from authenticated identity linking."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class OAuthLoginTransaction:
    id: UUID
    provider: LoginIdentityProvider
    state_hash: str
    code_verifier_ciphertext: bytes
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.provider is LoginIdentityProvider.EMAIL:
            raise ValueError("Email is not an OAuth login provider.")
        if len(self.state_hash) != 64:
            raise ValueError("OAuth login state hash must be SHA-256-sized.")
        if self.expires_at.tzinfo is None:
            raise ValueError("OAuth login expiry must be timezone-aware.")
