"""Safe serialization boundary for a pending e-mail/password registration."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, replace
from uuid import UUID

MAX_VERIFICATION_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class PendingEmailPasswordRegistration:
    """Values kept in Redis until the owner proves access to the e-mail inbox.

    The e-mail is encrypted and the password is already Argon2id-hashed before
    this object is serialized.  Neither the raw password, code nor bearer token
    is ever placed in the Redis value.
    """

    registration_id: UUID
    email_ciphertext: bytes
    email_lookup_hash: str
    password_hash: str
    display_name: str
    verification_code_hash: str
    attempts: int = 0

    def __post_init__(self) -> None:
        if not self.email_ciphertext:
            raise ValueError("Pending registration email ciphertext must not be empty.")
        if len(self.email_lookup_hash) != 64:
            raise ValueError("Pending registration email lookup hash is invalid.")
        if not self.password_hash.startswith("$argon2id$"):
            raise ValueError("Pending registration password must use Argon2id.")
        if not self.display_name.strip() or len(self.display_name) > 64:
            raise ValueError("Pending registration display name is invalid.")
        if len(self.verification_code_hash) != 64:
            raise ValueError("Pending registration code hash is invalid.")
        if not 0 <= self.attempts <= MAX_VERIFICATION_ATTEMPTS:
            raise ValueError("Pending registration attempts are invalid.")

    def with_attempts(self, attempts: int) -> PendingEmailPasswordRegistration:
        """Return a copy with the bounded failed-attempt counter advanced."""
        return replace(self, attempts=attempts)

    def to_json(self) -> str:
        """Serialize only the encrypted/hashed representation kept in Redis."""
        return json.dumps(
            {
                "registration_id": str(self.registration_id),
                "email_ciphertext": base64.urlsafe_b64encode(self.email_ciphertext).decode("ascii"),
                "email_lookup_hash": self.email_lookup_hash,
                "password_hash": self.password_hash,
                "display_name": self.display_name,
                "verification_code_hash": self.verification_code_hash,
                "attempts": self.attempts,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> PendingEmailPasswordRegistration | None:
        """Decode untrusted Redis data without allowing malformed state to escape."""
        try:
            payload = json.loads(value)
            if not isinstance(payload, dict):
                return None
            ciphertext = base64.urlsafe_b64decode(payload["email_ciphertext"])
            attempts = payload.get("attempts", 0)
            if not isinstance(attempts, int):
                return None
            return cls(
                registration_id=UUID(payload["registration_id"]),
                email_ciphertext=ciphertext,
                email_lookup_hash=payload["email_lookup_hash"],
                password_hash=payload["password_hash"],
                display_name=payload["display_name"],
                verification_code_hash=payload["verification_code_hash"],
                attempts=attempts,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            binascii.Error,
            json.JSONDecodeError,
        ):
            return None
