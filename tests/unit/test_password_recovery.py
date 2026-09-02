from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.complete_password_recovery import (
    CompletePasswordRecovery,
    CompletePasswordRecoveryCommand,
    PasswordRecoveryCompletionRejectedError,
)
from muxivo_console.application.request_password_recovery import (
    RequestPasswordRecovery,
    RequestPasswordRecoveryCommand,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import EmailPasswordAccount, UserStatus
from muxivo_console.domain.password_recovery import PasswordRecoveryTransaction


class SequenceIdentifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class Normalizer:
    def normalize(self, value: str) -> str:
        if "@" not in value:
            raise ValueError("Invalid email.")
        return value.strip().lower()


class LookupHasher:
    def lookup_hash(self, normalized_email: str) -> str:
        return f"lookup:{normalized_email}".ljust(64, "_")


class TokenIssuer:
    def issue(self) -> str:
        return "opaque-recovery-token"


class TokenHasher:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def hash(self, raw_token: str) -> str:
        self.tokens.append(raw_token)
        return "a" * 64


class Passwords:
    def __init__(self) -> None:
        self.hash_calls: list[str] = []

    def hash(self, plaintext_password: str) -> str:
        self.hash_calls.append(plaintext_password)
        return "$argon2id$new-password-hash"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        return bool(encoded_hash and plaintext_password)


class Accounts:
    def __init__(self, account: EmailPasswordAccount | None) -> None:
        self.account = account
        self.lookup_hash: str | None = None

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None:
        self.lookup_hash = email_lookup_hash
        return self.account


class RecoveryTransactions:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.transaction: PasswordRecoveryTransaction | None = None
        self.audit_event: AuditEvent | None = None

    async def create(
        self, *, transaction: PasswordRecoveryTransaction, audit_event: AuditEvent
    ) -> bool:
        self.transaction = transaction
        self.audit_event = audit_event
        return self.result


class RecoveryNotifier:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def send(self, **arguments) -> None:
        self.arguments = arguments


class RecoveryCompletionWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.arguments: dict[str, object] | None = None

    async def complete(self, **arguments) -> bool:
        self.arguments = arguments
        return self.result


@pytest.mark.asyncio
async def test_recovery_request_creates_hashed_token_and_notifies_active_account() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    user_id, transaction_id, audit_id, correlation_id = uuid4(), uuid4(), uuid4(), uuid4()
    token_hasher = TokenHasher()
    transactions = RecoveryTransactions()
    notifier = RecoveryNotifier()
    use_case = RequestPasswordRecovery(
        identifiers=SequenceIdentifiers([transaction_id, audit_id]),
        clock=FixedClock(now),
        email_normalizer=Normalizer(),
        email_lookup_hasher=LookupHasher(),
        token_issuer=TokenIssuer(),
        token_hasher=token_hasher,
        accounts=Accounts(EmailPasswordAccount(user_id, UserStatus.ACTIVE, "$argon2id$hash")),
        transactions=transactions,
        notifier=notifier,
    )

    await use_case.execute(RequestPasswordRecoveryCommand(" Creator@Example.com ", correlation_id))

    assert token_hasher.tokens == ["opaque-recovery-token"]
    assert transactions.transaction is not None
    assert transactions.transaction.id == transaction_id
    assert transactions.transaction.user_id == user_id
    assert transactions.transaction.token_hash == "a" * 64
    assert transactions.transaction.expires_at == now + timedelta(minutes=30)
    assert transactions.audit_event is not None
    assert transactions.audit_event.id == audit_id
    assert transactions.audit_event.action == "auth.password_recovery_requested"
    assert notifier.arguments is not None
    assert notifier.arguments["recipient_email"] == "creator@example.com"
    assert notifier.arguments["raw_token"] == "opaque-recovery-token"


@pytest.mark.asyncio
async def test_recovery_request_is_anti_enumeration_for_missing_account() -> None:
    token_hasher = TokenHasher()
    transactions = RecoveryTransactions()
    notifier = RecoveryNotifier()
    use_case = RequestPasswordRecovery(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        clock=FixedClock(datetime(2026, 8, 19, 12, tzinfo=UTC)),
        email_normalizer=Normalizer(),
        email_lookup_hasher=LookupHasher(),
        token_issuer=TokenIssuer(),
        token_hasher=token_hasher,
        accounts=Accounts(None),
        transactions=transactions,
        notifier=notifier,
    )

    await use_case.execute(RequestPasswordRecoveryCommand("missing@example.com", uuid4()))

    assert token_hasher.tokens == ["opaque-recovery-token"]
    assert transactions.transaction is None
    assert notifier.arguments is None


@pytest.mark.asyncio
async def test_recovery_completion_hashes_token_and_password_then_delegates_atomic_write() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    audit_id, correlation_id = uuid4(), uuid4()
    token_hasher = TokenHasher()
    passwords = Passwords()
    writer = RecoveryCompletionWriter()
    use_case = CompletePasswordRecovery(
        identifiers=SequenceIdentifiers([audit_id]),
        clock=FixedClock(now),
        token_hasher=token_hasher,
        password_hasher=passwords,
        completions=writer,
    )

    await use_case.execute(
        CompletePasswordRecoveryCommand(
            token="opaque-recovery-token",
            new_password="new-secure-password",
            correlation_id=correlation_id,
        )
    )

    assert token_hasher.tokens == ["opaque-recovery-token"]
    assert passwords.hash_calls == ["new-secure-password"]
    assert writer.arguments == {
        "token_hash": "a" * 64,
        "password_hash": "$argon2id$new-password-hash",
        "completed_at": now,
        "audit_id": audit_id,
        "correlation_id": correlation_id,
    }


@pytest.mark.asyncio
async def test_recovery_completion_rejects_invalid_or_consumed_token() -> None:
    use_case = CompletePasswordRecovery(
        identifiers=SequenceIdentifiers([uuid4()]),
        clock=FixedClock(datetime(2026, 8, 19, 12, tzinfo=UTC)),
        token_hasher=TokenHasher(),
        password_hasher=Passwords(),
        completions=RecoveryCompletionWriter(result=False),
    )

    with pytest.raises(PasswordRecoveryCompletionRejectedError):
        await use_case.execute(
            CompletePasswordRecoveryCommand(
                token="opaque-recovery-token",
                new_password="new-secure-password",
                correlation_id=uuid4(),
            )
        )
