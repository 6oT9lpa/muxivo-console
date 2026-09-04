from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest
from muxivo_console.application.complete_email_password_registration import (
    CompleteEmailPasswordRegistration,
)
from muxivo_console.application.email_password_registration_verification_rejected_error import (
    EmailPasswordRegistrationVerificationRejectedError,
)
from muxivo_console.application.start_email_password_registration import (
    StartEmailPasswordRegistration,
)
from muxivo_console.application.start_email_password_registration_command import (
    StartEmailPasswordRegistrationCommand,
)
from muxivo_console.application.verify_email_password_registration import (
    VerifyEmailPasswordRegistration,
)
from muxivo_console.application.verify_email_password_registration_command import (
    VerifyEmailPasswordRegistrationCommand,
)
from muxivo_console.domain.identity import EmailPasswordRegistration, UserStatus
from muxivo_console.infrastructure.in_memory_one_time_token_store import InMemoryOneTimeTokenStore


class Identifiers:
    def __init__(self) -> None:
        self.values = [uuid4() for _ in range(8)]

    def new(self):
        return self.values.pop(0)


class Clock:
    def now(self):
        return datetime(2026, 8, 22, 12, tzinfo=UTC)


class Normalizer:
    def normalize(self, value: str) -> str:
        return value.strip().lower()


class Protector:
    def encrypt(self, normalized_email: str) -> bytes:
        return f"encrypted:{normalized_email}".encode()

    def decrypt(self, ciphertext: bytes) -> str:
        return ciphertext.decode().removeprefix("encrypted:")

    def lookup_hash(self, normalized_email: str) -> str:
        return sha256(normalized_email.encode()).hexdigest()


class Passwords:
    def hash(self, plaintext_password: str) -> str:
        return "$argon2id$test-hash"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        return bool(encoded_hash and plaintext_password)


class TokenIssuer:
    def issue(self) -> str:
        return "opaque-pending-token"


class TokenHasher:
    def hash(self, raw_value: str) -> str:
        return sha256(raw_value.encode()).hexdigest()


class Accounts:
    async def find_by_email_lookup_hash(self, *, email_lookup_hash: str):
        return None


class ExistingAccount:
    async def find_by_email_lookup_hash(self, *, email_lookup_hash: str):
        return object()


class Notifier:
    def __init__(self) -> None:
        self.code = None

    async def send(self, **kwargs) -> None:
        self.code = kwargs["verification_code"]


class RegistrationWriter:
    def __init__(self) -> None:
        self.registration: EmailPasswordRegistration | None = None
        self.audit_event = None

    async def register(self, *, registration, audit_event) -> bool:
        self.registration = registration
        self.audit_event = audit_event
        return True


class FailingNotifier:
    async def send(self, **kwargs) -> None:
        raise RuntimeError("smtp failed")


def _start(store: InMemoryOneTimeTokenStore, notifier: Notifier) -> StartEmailPasswordRegistration:
    return StartEmailPasswordRegistration(
        identifiers=Identifiers(),
        clock=Clock(),
        email_normalizer=Normalizer(),
        email_protector=Protector(),
        password_hasher=Passwords(),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        accounts=Accounts(),
        pending_registrations=store,
        notifier=notifier,
    )


@pytest.mark.asyncio
async def test_start_stores_only_hashed_or_encrypted_registration_data_and_sends_code() -> None:
    store = InMemoryOneTimeTokenStore()
    notifier = Notifier()
    use_case = _start(store, notifier)

    result = await use_case.execute(
        StartEmailPasswordRegistrationCommand(
            email=" Creator@Example.com ",
            password="a-long-enough-password",
            display_name="Creator",
            correlation_id=uuid4(),
        )
    )

    assert result.raw_token == "opaque-pending-token"
    assert notifier.code is not None and len(notifier.code) == 6
    stored = await store.get(
        key=f"muxivo-console:registration-verification:{TokenHasher().hash('opaque-pending-token')}"
    )
    assert stored is not None
    assert "a-long-enough-password" not in stored
    assert notifier.code not in stored


@pytest.mark.asyncio
async def test_existing_account_stays_enumeration_safe_and_is_not_delivered_a_code() -> None:
    store = InMemoryOneTimeTokenStore()
    notifier = Notifier()
    use_case = _start(store, notifier)
    use_case.accounts = ExistingAccount()

    result = await use_case.execute(
        StartEmailPasswordRegistrationCommand(
            email="existing@example.com",
            password="a-long-enough-password",
            display_name="Creator",
            correlation_id=uuid4(),
        )
    )

    assert result.raw_token is None
    assert notifier.code is None


@pytest.mark.asyncio
async def test_delivery_failure_removes_pending_flow_and_does_not_return_a_token() -> None:
    store = InMemoryOneTimeTokenStore()
    use_case = _start(store, FailingNotifier())

    with pytest.raises(ConnectionError):
        await use_case.execute(
            StartEmailPasswordRegistrationCommand(
                email="creator@example.com",
                password="a-long-enough-password",
                display_name="Creator",
                correlation_id=uuid4(),
            )
        )

    assert (
        await store.get(
            key=f"muxivo-console:registration-verification:{TokenHasher().hash('opaque-pending-token')}"
        )
        is None
    )


@pytest.mark.asyncio
async def test_correct_code_completes_registration_once_and_replay_is_rejected() -> None:
    store = InMemoryOneTimeTokenStore()
    notifier = Notifier()
    start = _start(store, notifier)
    correlation_id = uuid4()
    await start.execute(
        StartEmailPasswordRegistrationCommand(
            email="creator@example.com",
            password="a-long-enough-password",
            display_name="Creator",
            correlation_id=correlation_id,
        )
    )
    writer = RegistrationWriter()
    registrar = CompleteEmailPasswordRegistration(
        identifiers=Identifiers(),
        email_normalizer=Normalizer(),
        email_protector=Protector(),
        registrations=writer,
    )
    verify = VerifyEmailPasswordRegistration(
        token_hasher=TokenHasher(),
        email_protector=Protector(),
        pending_registrations=store,
        registrations=registrar,
    )

    await verify.execute(
        VerifyEmailPasswordRegistrationCommand(
            token="opaque-pending-token",
            code=notifier.code,
            correlation_id=uuid4(),
        )
    )

    assert writer.registration is not None
    assert writer.registration.user.status is UserStatus.ACTIVE
    assert writer.audit_event.action == "auth.email_password_registration_verified"
    with pytest.raises(EmailPasswordRegistrationVerificationRejectedError):
        await verify.execute(
            VerifyEmailPasswordRegistrationCommand(
                token="opaque-pending-token",
                code=notifier.code,
                correlation_id=uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_wrong_code_increments_attempts_without_consuming_the_pending_flow() -> None:
    store = InMemoryOneTimeTokenStore()
    notifier = Notifier()
    start = _start(store, notifier)
    await start.execute(
        StartEmailPasswordRegistrationCommand(
            email="creator@example.com",
            password="a-long-enough-password",
            display_name="Creator",
            correlation_id=uuid4(),
        )
    )
    writer = RegistrationWriter()
    verify = VerifyEmailPasswordRegistration(
        token_hasher=TokenHasher(),
        email_protector=Protector(),
        pending_registrations=store,
        registrations=CompleteEmailPasswordRegistration(
            identifiers=Identifiers(),
            email_normalizer=Normalizer(),
            email_protector=Protector(),
            registrations=writer,
        ),
    )

    with pytest.raises(EmailPasswordRegistrationVerificationRejectedError):
        await verify.execute(
            VerifyEmailPasswordRegistrationCommand(
                token="opaque-pending-token",
                code="000000",
                correlation_id=uuid4(),
            )
        )
    assert await store.get(
        key=f"muxivo-console:registration-verification:{TokenHasher().hash('opaque-pending-token')}"
    )
    assert writer.registration is None
