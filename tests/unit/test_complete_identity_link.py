from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from muxivo_console.application.complete_identity_link import (
    CompleteIdentityLink,
    CompleteIdentityLinkCommand,
    IdentityLinkCompletionRejectedError,
)
from muxivo_console.application.link_verified_identity import LinkVerifiedIdentityCommand
from muxivo_console.domain.identity import LoginIdentity, LoginIdentityProvider
from muxivo_console.domain.identity_linking import IdentityLinkTransaction


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 9, tzinfo=UTC)


class Hasher:
    def __init__(self) -> None:
        self.token: str | None = None

    def hash(self, token: str) -> str:
        self.token = token
        return "s" * 64


class Secrets:
    def decrypt(self, ciphertext: bytes) -> str:
        assert ciphertext == b"encrypted-verifier"
        return "pkce-verifier"


class Transactions:
    def __init__(self, transaction: IdentityLinkTransaction | None) -> None:
        self.transaction = transaction
        self.arguments = None

    async def consume(self, **arguments) -> IdentityLinkTransaction | None:
        self.arguments = arguments
        return self.transaction


class Provider:
    def __init__(self, subject: str = "123456789012345678") -> None:
        self.subject = subject
        self.arguments = None

    async def resolve_subject(self, **arguments) -> str:
        self.arguments = arguments
        return self.subject


class Linker:
    def __init__(self, identity: LoginIdentity) -> None:
        self.identity = identity
        self.command: LinkVerifiedIdentityCommand | None = None

    async def execute(self, command: LinkVerifiedIdentityCommand) -> LoginIdentity:
        self.command = command
        return self.identity


def transaction(
    provider: LoginIdentityProvider = LoginIdentityProvider.DISCORD,
) -> IdentityLinkTransaction:
    return IdentityLinkTransaction(
        id=uuid4(),
        user_id=uuid4(),
        provider=provider,
        state_hash="s" * 64,
        code_verifier_ciphertext=b"encrypted-verifier",
        expires_at=datetime(2026, 8, 9, tzinfo=UTC) + timedelta(minutes=10),
        consumed_at=datetime(2026, 8, 9, tzinfo=UTC),
    )


def command(
    provider: LoginIdentityProvider = LoginIdentityProvider.DISCORD,
) -> CompleteIdentityLinkCommand:
    return CompleteIdentityLinkCommand(provider, "raw-state", "oauth-code", uuid4())


@pytest.mark.asyncio
async def test_consumes_state_once_then_resolves_and_links_verified_provider_subject() -> None:
    stored = transaction()
    provider = Provider()
    identity = LoginIdentity(
        uuid4(), stored.user_id, LoginIdentityProvider.DISCORD, provider.subject
    )
    linker = Linker(identity)
    hasher = Hasher()
    transactions = Transactions(stored)
    completed = await CompleteIdentityLink(
        Clock(), hasher, Secrets(), transactions, provider, linker
    ).execute(command())

    assert completed == identity
    assert hasher.token == "raw-state"
    assert transactions.arguments == {"state_hash": "s" * 64, "consumed_at": Clock().now()}
    assert provider.arguments == {
        "authorization_code": "oauth-code",
        "code_verifier": "pkce-verifier",
    }
    assert linker.command.actor_id == stored.user_id
    assert linker.command.verified_provider_subject == provider.subject


@pytest.mark.asyncio
async def test_missing_claimed_or_mismatched_state_never_calls_provider() -> None:
    stored = transaction(LoginIdentityProvider.DISCORD)
    provider = Provider()
    identity = LoginIdentity(
        uuid4(), stored.user_id, LoginIdentityProvider.DISCORD, provider.subject
    )
    linker = Linker(identity)
    use_case = CompleteIdentityLink(
        Clock(), Hasher(), Secrets(), Transactions(stored), provider, linker
    )

    with pytest.raises(IdentityLinkCompletionRejectedError):
        await use_case.execute(command(LoginIdentityProvider.TWITCH))

    assert provider.arguments is None
    assert linker.command is None
