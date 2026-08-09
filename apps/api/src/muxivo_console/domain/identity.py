"""First-party identity entities owned by Muxivo Console.

These objects deliberately contain only data that Console owns. A Discord or
Twitch login is a future ``LoginIdentity`` provider, never a platform
connection or a platform-role grant.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class LoginIdentityProvider(StrEnum):
    EMAIL = "email"
    DISCORD = "discord"
    TWITCH = "twitch"
    GOOGLE = "google"
    YANDEX = "yandex"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    status: UserStatus
    display_name: str

    def __post_init__(self) -> None:
        if not self.display_name.strip() or len(self.display_name) > 64:
            raise ValueError("Display name must contain 1 to 64 non-blank characters.")


@dataclass(frozen=True, slots=True)
class LoginIdentity:
    id: UUID
    user_id: UUID
    provider: LoginIdentityProvider
    provider_subject: str

    def __post_init__(self) -> None:
        if not self.provider_subject or len(self.provider_subject) > 255:
            raise ValueError("Provider subject must contain 1 to 255 characters.")


@dataclass(frozen=True, slots=True)
class UserEmail:
    id: UUID
    user_id: UUID
    ciphertext: bytes
    lookup_hash: str
    is_primary: bool = True

    def __post_init__(self) -> None:
        if not self.ciphertext:
            raise ValueError("Email ciphertext must not be empty.")
        if len(self.lookup_hash) != 64:
            raise ValueError("Email lookup hash must be a SHA-256-sized hex digest.")


@dataclass(frozen=True, slots=True)
class PasswordCredential:
    user_id: UUID
    password_hash: str

    def __post_init__(self) -> None:
        if not self.password_hash.startswith("$argon2id$"):
            raise ValueError("Password credential must use Argon2id.")


@dataclass(frozen=True, slots=True)
class EmailPasswordRegistration:
    """Atomic data set required to create an email/password Console account."""

    user: User
    identity: LoginIdentity
    email: UserEmail
    password_credential: PasswordCredential

    def __post_init__(self) -> None:
        user_id = self.user.id
        if any(
            related_user_id != user_id
            for related_user_id in (
                self.identity.user_id,
                self.email.user_id,
                self.password_credential.user_id,
            )
        ):
            raise ValueError("Email/password registration records must belong to one user.")
        if self.identity.provider is not LoginIdentityProvider.EMAIL:
            raise ValueError("Email/password registration must create an email identity.")


@dataclass(frozen=True, slots=True)
class EmailPasswordAccount:
    """Minimal authentication projection; it never contains an e-mail address."""

    user_id: UUID
    status: UserStatus
    password_hash: str

    def __post_init__(self) -> None:
        if not self.password_hash.startswith("$argon2id$"):
            raise ValueError("Email/password account must hold an Argon2id credential.")
