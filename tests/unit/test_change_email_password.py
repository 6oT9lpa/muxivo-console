from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.change_email_password import (
    ChangeEmailPassword,
    ChangeEmailPasswordCommand,
    PasswordChangeRejectedError,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import PasswordCredential, UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel


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


class UserStatuses:
    def __init__(self, status: UserStatus | None) -> None:
        self.status = status
        self.user_id: UUID | None = None

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        self.user_id = user_id
        return self.status


class Credentials:
    def __init__(self, credential: PasswordCredential | None) -> None:
        self.credential = credential
        self.user_id: UUID | None = None

    async def find_for_user(self, *, user_id: UUID) -> PasswordCredential | None:
        self.user_id = user_id
        return self.credential


class CredentialWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.user_id: UUID | None = None
        self.password_hash: str | None = None
        self.changed_at: datetime | None = None
        self.audit_event: AuditEvent | None = None

    async def change_password(
        self, *, user_id: UUID, password_hash: str, changed_at, audit_event: AuditEvent
    ) -> bool:
        self.user_id = user_id
        self.password_hash = password_hash
        self.changed_at = changed_at
        self.audit_event = audit_event
        return self.result


class Passwords:
    def __init__(self, matches: bool = True) -> None:
        self.matches = matches
        self.hash_calls: list[str] = []
        self.verify_calls: list[tuple[str, str]] = []

    def hash(self, plaintext_password: str) -> str:
        self.hash_calls.append(plaintext_password)
        return "$argon2id$new-password-hash"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        self.verify_calls.append((encoded_hash, plaintext_password))
        return self.matches


def principal(
    now: datetime,
    *,
    user_id: UUID | None = None,
    assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
    age: timedelta = timedelta(minutes=1),
) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=user_id or uuid4(),
        session_id=uuid4(),
        assurance_level=assurance_level,
        authenticated_at=now - age,
    )


def use_case(
    *,
    now: datetime,
    user_status: UserStatus | None = UserStatus.ACTIVE,
    credential: PasswordCredential | None,
    passwords: Passwords | None = None,
    writer: CredentialWriter | None = None,
    audit_id: UUID | None = None,
) -> ChangeEmailPassword:
    clock = FixedClock(now)
    return ChangeEmailPassword(
        identifiers=SequenceIdentifiers([audit_id or uuid4()]),
        clock=clock,
        user_statuses=UserStatuses(user_status),
        credentials=Credentials(credential),
        credential_writer=writer or CredentialWriter(),
        password_hasher=passwords or Passwords(),
        recent_authentication=RequireRecentAuthentication(clock),
    )


@pytest.mark.asyncio
async def test_changes_password_after_recent_authentication_and_writes_audit() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    actor_id = uuid4()
    audit_id = uuid4()
    correlation_id = uuid4()
    writer = CredentialWriter()
    passwords = Passwords()
    command = ChangeEmailPasswordCommand(
        principal=principal(now, user_id=actor_id),
        current_password="current-password",
        new_password="new-secure-password",
        correlation_id=correlation_id,
    )

    await use_case(
        now=now,
        credential=PasswordCredential(actor_id, "$argon2id$old-password-hash"),
        passwords=passwords,
        writer=writer,
        audit_id=audit_id,
    ).execute(command)

    assert passwords.verify_calls == [("$argon2id$old-password-hash", "current-password")]
    assert passwords.hash_calls == ["new-secure-password"]
    assert writer.user_id == actor_id
    assert writer.password_hash == "$argon2id$new-password-hash"
    assert writer.changed_at == now
    assert writer.audit_event is not None
    assert writer.audit_event.id == audit_id
    assert writer.audit_event.correlation_id == correlation_id
    assert writer.audit_event.action == "auth.password_changed"
    assert writer.audit_event.resource_id == str(actor_id)


@pytest.mark.asyncio
async def test_rejects_stale_authentication_before_password_verification() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    actor_id = uuid4()
    passwords = Passwords()
    writer = CredentialWriter()

    with pytest.raises(RecentAuthenticationRequiredError):
        await use_case(
            now=now,
            credential=PasswordCredential(actor_id, "$argon2id$old-password-hash"),
            passwords=passwords,
            writer=writer,
        ).execute(
            ChangeEmailPasswordCommand(
                principal=principal(now, user_id=actor_id, age=timedelta(minutes=16)),
                current_password="current-password",
                new_password="new-secure-password",
                correlation_id=uuid4(),
            )
        )

    assert passwords.verify_calls == []
    assert passwords.hash_calls == []
    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_rejects_wrong_current_password_without_writing() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    actor_id = uuid4()
    writer = CredentialWriter()

    with pytest.raises(PasswordChangeRejectedError):
        await use_case(
            now=now,
            credential=PasswordCredential(actor_id, "$argon2id$old-password-hash"),
            passwords=Passwords(matches=False),
            writer=writer,
        ).execute(
            ChangeEmailPasswordCommand(
                principal=principal(now, user_id=actor_id),
                current_password="wrong-password",
                new_password="new-secure-password",
                correlation_id=uuid4(),
            )
        )

    assert writer.audit_event is None


@pytest.mark.asyncio
async def test_missing_password_identity_performs_hash_work_and_fails_closed() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    passwords = Passwords()

    with pytest.raises(PasswordChangeRejectedError):
        await use_case(now=now, credential=None, passwords=passwords).execute(
            ChangeEmailPasswordCommand(
                principal=principal(now),
                current_password="current-password",
                new_password="new-secure-password",
                correlation_id=uuid4(),
            )
        )

    assert passwords.hash_calls == ["current-password"]


@pytest.mark.asyncio
async def test_rejects_reused_password_after_current_password_verification() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    actor_id = uuid4()
    writer = CredentialWriter()

    with pytest.raises(PasswordChangeRejectedError):
        await use_case(
            now=now,
            credential=PasswordCredential(actor_id, "$argon2id$old-password-hash"),
            writer=writer,
        ).execute(
            ChangeEmailPasswordCommand(
                principal=principal(now, user_id=actor_id),
                current_password="same-password",
                new_password="same-password",
                correlation_id=uuid4(),
            )
        )

    assert writer.audit_event is None
