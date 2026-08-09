from collections import deque
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.begin_identity_link import (
    BeginIdentityLink,
    BeginIdentityLinkCommand,
    IdentityLinkStartRejectedError,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider, UserStatus
from muxivo_console.domain.identity_linking import IdentityLinkTransaction


class Identifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 9, tzinfo=UTC)


class UserStatuses:
    def __init__(self, status: UserStatus | None) -> None:
        self.status = status

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


class Tokens:
    def __init__(self) -> None:
        self.values = iter(("state-token", "pkce-verifier"))

    def issue(self) -> str:
        return next(self.values)


class Hasher:
    def hash(self, raw_token: str) -> str:
        assert raw_token == "state-token"
        return "h" * 64


class Secrets:
    def encrypt(self, plaintext: str) -> bytes:
        assert plaintext == "pkce-verifier"
        return b"encrypted-pkce-verifier"


class Transactions:
    def __init__(self, created: bool = True) -> None:
        self.created = created
        self.transaction: IdentityLinkTransaction | None = None
        self.audit_event: AuditEvent | None = None

    async def create(
        self, *, transaction: IdentityLinkTransaction, audit_event: AuditEvent
    ) -> bool:
        self.transaction = transaction
        self.audit_event = audit_event
        return self.created


def command(
    provider: LoginIdentityProvider = LoginIdentityProvider.DISCORD,
) -> BeginIdentityLinkCommand:
    return BeginIdentityLinkCommand(uuid4(), provider, uuid4())


@pytest.mark.asyncio
async def test_starts_active_user_link_with_opaque_state_encrypted_pkce_and_audit() -> None:
    transaction_id, audit_id = uuid4(), uuid4()
    transactions = Transactions()
    started = await BeginIdentityLink(
        Identifiers([transaction_id, audit_id]),
        Clock(),
        UserStatuses(UserStatus.ACTIVE),
        Tokens(),
        Hasher(),
        Secrets(),
        transactions,
    ).execute(command())

    assert started.state == "state-token"
    assert "state-token" not in repr(started)
    assert started.code_challenge == "S-YYjGPeiHjsbIXpqrbVjcGUQn7X-4T468hBrBqm8pA"
    assert transactions.transaction.state_hash == "h" * 64
    assert transactions.transaction.code_verifier_ciphertext == b"encrypted-pkce-verifier"
    assert transactions.audit_event.action == "identity.link_started"


@pytest.mark.asyncio
async def test_rejects_inactive_or_email_link_before_persisting() -> None:
    transactions = Transactions()
    use_case = BeginIdentityLink(
        Identifiers([uuid4(), uuid4()]),
        Clock(),
        UserStatuses(UserStatus.SUSPENDED),
        Tokens(),
        Hasher(),
        Secrets(),
        transactions,
    )

    with pytest.raises(IdentityLinkStartRejectedError):
        await use_case.execute(command())
    assert transactions.transaction is None
