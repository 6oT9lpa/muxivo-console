from collections import deque
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.register_email_password import (
    RegisterEmailPassword,
    RegisterEmailPasswordCommand,
    RegistrationRejectedError,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import EmailPasswordRegistration, UserStatus


class SequenceIdentifiers:
    def __init__(self, values: list[UUID]) -> None:
        self.values = deque(values)

    def new(self) -> UUID:
        return self.values.popleft()


class Normalizer:
    def normalize(self, value: str) -> str:
        return value.strip().lower()


class Protector:
    def encrypt(self, normalized_email: str) -> bytes:
        return f"encrypted:{normalized_email}".encode()

    def lookup_hash(self, normalized_email: str) -> str:
        return "a" * 64


class Hasher:
    def hash(self, plaintext_password: str) -> str:
        return "$argon2id$test-hash"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        return encoded_hash == "$argon2id$test-hash" and bool(plaintext_password)


class RegistrationWriter:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.registration: EmailPasswordRegistration | None = None
        self.audit_event: AuditEvent | None = None

    async def register(
        self, *, registration: EmailPasswordRegistration, audit_event: AuditEvent
    ) -> bool:
        self.registration = registration
        self.audit_event = audit_event
        return self.result


def command() -> RegisterEmailPasswordCommand:
    return RegisterEmailPasswordCommand(
        email="  creator@example.com ",
        password="a-long-enough-password",
        display_name="Creator",
        correlation_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_registration_creates_pending_user_identity_and_secret_free_audit_event() -> None:
    ids = [uuid4() for _ in range(5)]
    writer = RegistrationWriter(result=True)
    use_case = RegisterEmailPassword(
        SequenceIdentifiers(ids), Normalizer(), Protector(), Hasher(), writer
    )

    user_id = await use_case.execute(command())

    assert user_id == writer.registration.user.id
    assert writer.registration.user.status is UserStatus.PENDING_VERIFICATION
    assert writer.registration.identity.provider_subject == "a" * 64
    assert writer.registration.email.ciphertext == b"encrypted:creator@example.com"
    assert writer.registration.password_credential.password_hash == "$argon2id$test-hash"
    assert writer.audit_event.action == "auth.email_password_registration"
    assert "creator@example.com" not in repr(writer.audit_event)
    assert "a-long-enough-password" not in repr(writer.audit_event)


@pytest.mark.asyncio
async def test_registration_does_not_reveal_identity_conflicts() -> None:
    ids = SequenceIdentifiers([uuid4() for _ in range(5)])
    use_case = RegisterEmailPassword(
        ids, Normalizer(), Protector(), Hasher(), RegistrationWriter(False)
    )

    with pytest.raises(RegistrationRejectedError, match="Registration could not be completed"):
        await use_case.execute(command())


@pytest.mark.asyncio
async def test_registration_rejects_short_password_before_writing() -> None:
    ids = SequenceIdentifiers([uuid4() for _ in range(5)])
    writer = RegistrationWriter(True)
    use_case = RegisterEmailPassword(ids, Normalizer(), Protector(), Hasher(), writer)
    invalid_command = RegisterEmailPasswordCommand(
        email="creator@example.com",
        password="short",
        display_name="Creator",
        correlation_id=uuid4(),
    )

    with pytest.raises(RegistrationRejectedError):
        await use_case.execute(invalid_command)

    assert writer.registration is None
