from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.complete_oauth_login import (
    CompleteOAuthLogin,
    OAuthLoginCompletionRejectedError,
)
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.oauth_login import OAuthLoginTransaction
from muxivo_console.domain.sessions import SessionAssuranceLevel


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 19, 12, tzinfo=UTC)


class Hasher:
    def hash(self, value: str) -> str:
        return "a" * 64


class Secrets:
    def decrypt(self, _: bytes) -> str:
        return "verifier"


class Transactions:
    def __init__(self, transaction: OAuthLoginTransaction | None) -> None:
        self.transaction = transaction

    async def consume(self, **_: object) -> OAuthLoginTransaction | None:
        return self.transaction


class Provider:
    async def resolve_subject(self, **_: object) -> str:
        return "123456789012345678"


class Identities:
    def __init__(self, user_id: UUID | None) -> None:
        self.user_id = user_id

    async def find_user_id(self, **_: object) -> UUID | None:
        return self.user_id


class Sessions:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command) -> IssuedBrowserSession:
        self.command = command
        return IssuedBrowserSession(
            uuid4(), "token", "csrf", Clock().now() + timedelta(days=1),
            SessionAssuranceLevel.PASSWORD,
        )


def transaction() -> OAuthLoginTransaction:
    return OAuthLoginTransaction(
        uuid4(), LoginIdentityProvider.DISCORD, "a" * 64, b"ciphertext",
        Clock().now() + timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_creates_session_only_for_existing_verified_provider_identity() -> None:
    user_id, sessions = uuid4(), Sessions()
    use_case = CompleteOAuthLogin(
        Clock(), Hasher(), Secrets(), Transactions(transaction()), Provider(),
        Identities(user_id), sessions,
    )
    issued = await use_case.execute(
        provider=LoginIdentityProvider.DISCORD, state="state", authorization_code="code",
        correlation_id=uuid4(),
    )

    assert issued.assurance_level is SessionAssuranceLevel.PASSWORD
    assert sessions.command.user_id == user_id


@pytest.mark.asyncio
async def test_rejects_unknown_or_replayed_oauth_state_without_creating_session() -> None:
    sessions = Sessions()
    with pytest.raises(OAuthLoginCompletionRejectedError):
        use_case = CompleteOAuthLogin(
            Clock(), Hasher(), Secrets(), Transactions(None), Provider(),
            Identities(uuid4()), sessions,
        )
        await use_case.execute(
            provider=LoginIdentityProvider.DISCORD, state="state", authorization_code="code",
            correlation_id=uuid4(),
        )
    assert sessions.command is None
