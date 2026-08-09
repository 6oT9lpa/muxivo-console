from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.authenticate_email_password import (
    AuthenticateEmailPassword,
    AuthenticateEmailPasswordCommand,
    AuthenticationRejectedError,
)
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.domain.identity import EmailPasswordAccount, UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel


class Normalizer:
    def normalize(self, value: str) -> str:
        if value == "invalid":
            raise ValueError("invalid")
        return value.strip().lower()


class LookupHasher:
    def lookup_hash(self, normalized_email: str) -> str:
        return f"hash:{normalized_email}"


class Accounts:
    def __init__(self, account: EmailPasswordAccount | None) -> None:
        self.account = account
        self.received_lookup_hash: str | None = None

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None:
        self.received_lookup_hash = email_lookup_hash
        return self.account


class Passwords:
    def __init__(self, matches: bool = True) -> None:
        self.matches = matches
        self.hash_calls: list[str] = []
        self.verify_calls: list[tuple[str, str]] = []

    def hash(self, plaintext_password: str) -> str:
        self.hash_calls.append(plaintext_password)
        return "$argon2id$unknown-account-work-factor"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        self.verify_calls.append((encoded_hash, plaintext_password))
        return self.matches


class SessionCreator:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command):
        self.command = command
        return IssuedBrowserSession(
            id=uuid4(),
            raw_token="opaque-token",
            expires_at=datetime(2026, 8, 23, tzinfo=UTC),
            assurance_level=SessionAssuranceLevel.PASSWORD,
        )


def command() -> AuthenticateEmailPasswordCommand:
    return AuthenticateEmailPasswordCommand(" creator@example.com ", "password", uuid4())


def active_account(user_id: UUID) -> EmailPasswordAccount:
    return EmailPasswordAccount(user_id, UserStatus.ACTIVE, "$argon2id$stored-hash")


@pytest.mark.asyncio
async def test_authenticates_active_account_and_delegates_session_creation() -> None:
    user_id = uuid4()
    accounts = Accounts(active_account(user_id))
    passwords = Passwords()
    session_creator = SessionCreator()
    use_case = AuthenticateEmailPassword(
        Normalizer(), LookupHasher(), accounts, passwords, session_creator
    )

    issued = await use_case.execute(command())

    assert issued.raw_token == "opaque-token"
    assert accounts.received_lookup_hash == "hash:creator@example.com"
    assert passwords.verify_calls == [("$argon2id$stored-hash", "password")]
    assert session_creator.command.user_id == user_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account", "password_matches"),
    (
        (None, True),
        (
            EmailPasswordAccount(uuid4(), UserStatus.PENDING_VERIFICATION, "$argon2id$stored-hash"),
            True,
        ),
        (EmailPasswordAccount(uuid4(), UserStatus.ACTIVE, "$argon2id$stored-hash"), False),
    ),
)
async def test_rejects_missing_inactive_or_wrong_password_without_session(
    account: EmailPasswordAccount | None, password_matches: bool
) -> None:
    passwords = Passwords(password_matches)
    session_creator = SessionCreator()
    use_case = AuthenticateEmailPassword(
        Normalizer(), LookupHasher(), Accounts(account), passwords, session_creator
    )

    with pytest.raises(AuthenticationRejectedError, match="could not be completed"):
        await use_case.execute(command())

    assert session_creator.command is None


@pytest.mark.asyncio
async def test_missing_or_invalid_email_performs_password_hash_work_before_rejection() -> None:
    passwords = Passwords()
    use_case = AuthenticateEmailPassword(
        Normalizer(), LookupHasher(), Accounts(None), passwords, SessionCreator()
    )

    with pytest.raises(AuthenticationRejectedError):
        await use_case.execute(command())
    with pytest.raises(AuthenticationRejectedError):
        await use_case.execute(AuthenticateEmailPasswordCommand("invalid", "password", uuid4()))

    assert passwords.hash_calls == ["password", "password"]
