from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import uuid4

import pytest
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import (
    EmailPasswordRegistration,
    LoginIdentity,
    LoginIdentityProvider,
    PasswordCredential,
    User,
    UserEmail,
    UserStatus,
)
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    LoginIdentityRecord,
    PasswordCredentialRecord,
    UserEmailRecord,
    UserRecord,
)
from muxivo_console.infrastructure.persistence.registration_writer import (
    SqlAlchemyEmailPasswordRegistrationWriter,
)
from sqlalchemy.exc import IntegrityError


@dataclass
class FakeTransaction(AbstractAsyncContextManager[None]):
    exc_type: type[BaseException] | None = None

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.exc_type = exc_type
        return False


class FakeSession(AbstractAsyncContextManager[Self]):
    def __init__(self, *, integrity_error: bool = False) -> None:
        self.integrity_error = integrity_error
        self.records: tuple[object, ...] = ()
        self.transaction = FakeTransaction()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> FakeTransaction:
        return self.transaction

    def add_all(self, records: tuple[object, ...]) -> None:
        self.records = records

    async def flush(self) -> None:
        if self.integrity_error:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))


def registration() -> EmailPasswordRegistration:
    user_id = uuid4()
    return EmailPasswordRegistration(
        user=User(user_id, UserStatus.PENDING_VERIFICATION, "Creator"),
        identity=LoginIdentity(uuid4(), user_id, LoginIdentityProvider.EMAIL, "a" * 64),
        email=UserEmail(uuid4(), user_id, b"ciphertext", "a" * 64),
        password_credential=PasswordCredential(user_id, "$argon2id$test-hash"),
    )


def audit_event(user_id) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=user_id,
        organization_id=None,
        action="auth.email_password_registration",
        resource_type="user",
        resource_id=str(user_id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_writes_all_registration_rows_and_audit_event_in_one_transaction() -> None:
    session = FakeSession()
    payload = registration()

    created = await SqlAlchemyEmailPasswordRegistrationWriter(lambda: session).register(
        registration=payload, audit_event=audit_event(payload.user.id)
    )

    assert created is True
    assert session.transaction.exc_type is None
    assert tuple(type(record) for record in session.records) == (
        UserRecord,
        LoginIdentityRecord,
        UserEmailRecord,
        PasswordCredentialRecord,
        AuditEventRecord,
    )
    user_record = session.records[0]
    email_record = session.records[2]
    assert user_record.status == "pending_verification"
    assert email_record.email_ciphertext == b"ciphertext"


@pytest.mark.asyncio
async def test_reduces_unique_conflict_to_non_enumerating_failure() -> None:
    session = FakeSession(integrity_error=True)
    payload = registration()

    created = await SqlAlchemyEmailPasswordRegistrationWriter(lambda: session).register(
        registration=payload, audit_event=audit_event(payload.user.id)
    )

    assert created is False
    assert session.transaction.exc_type is IntegrityError
