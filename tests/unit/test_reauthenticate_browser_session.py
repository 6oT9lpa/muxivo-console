from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.reauthenticate_browser_session import (
    BrowserSessionReauthenticationRejectedError,
    ReauthenticateBrowserSession,
    ReauthenticateBrowserSessionCommand,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import PasswordCredential, UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class Identifiers:
    def __init__(self, value: UUID) -> None:
        self.value = value

    def new(self) -> UUID:
        return self.value


class UserStatuses:
    def __init__(self, status: UserStatus | None = UserStatus.ACTIVE) -> None:
        self.status = status

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


class Credentials:
    def __init__(self, credential: PasswordCredential | None) -> None:
        self.credential = credential

    async def find_for_user(self, *, user_id: UUID) -> PasswordCredential | None:
        return self.credential


class PasswordHasher:
    def __init__(self, matches: bool) -> None:
        self.matches = matches
        self.hash_calls = 0

    def hash(self, plaintext_password: str) -> str:
        self.hash_calls += 1
        return f"hash:{plaintext_password}"

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool:
        return self.matches


class SessionReauthenticationWriter:
    def __init__(self, updated: bool = True) -> None:
        self.updated = updated
        self.session_id: UUID | None = None
        self.audit_event: AuditEvent | None = None
        self.authenticated_at: datetime | None = None

    async def reauthenticate(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        authenticated_at: datetime,
        audit_event: AuditEvent,
    ) -> bool:
        self.session_id = session_id
        self.authenticated_at = authenticated_at
        self.audit_event = audit_event
        return self.updated


def principal(actor_id: UUID, session_id: UUID) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=actor_id,
        session_id=session_id,
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )


@pytest.mark.asyncio
async def test_reauthenticates_current_session_and_writes_audit() -> None:
    now = datetime(2026, 8, 22, 12, 30, tzinfo=UTC)
    actor_id, session_id, audit_id, correlation_id = uuid4(), uuid4(), uuid4(), uuid4()
    writer = SessionReauthenticationWriter()
    use_case = ReauthenticateBrowserSession(
        identifiers=Identifiers(audit_id),
        clock=FixedClock(now),
        user_statuses=UserStatuses(),
        credentials=Credentials(PasswordCredential(actor_id, "$argon2id$old")),
        password_hasher=PasswordHasher(matches=True),
        sessions=writer,
    )

    await use_case.execute(
        ReauthenticateBrowserSessionCommand(
            principal=principal(actor_id, session_id),
            current_password="correct-password",
            correlation_id=correlation_id,
        )
    )

    assert writer.session_id == session_id
    assert writer.authenticated_at == now
    assert writer.audit_event == AuditEvent(
        id=audit_id,
        correlation_id=correlation_id,
        actor_id=actor_id,
        organization_id=None,
        action="auth.session_reauthenticated",
        resource_type="auth_session",
        resource_id=str(session_id),
        result="succeeded",
    )


@pytest.mark.asyncio
async def test_reauthentication_rejects_wrong_password_without_writing_session() -> None:
    actor_id, session_id = uuid4(), uuid4()
    writer = SessionReauthenticationWriter()
    use_case = ReauthenticateBrowserSession(
        identifiers=Identifiers(uuid4()),
        clock=FixedClock(datetime(2026, 8, 22, tzinfo=UTC)),
        user_statuses=UserStatuses(),
        credentials=Credentials(PasswordCredential(actor_id, "$argon2id$old")),
        password_hasher=PasswordHasher(matches=False),
        sessions=writer,
    )

    with pytest.raises(BrowserSessionReauthenticationRejectedError):
        await use_case.execute(
            ReauthenticateBrowserSessionCommand(
                principal=principal(actor_id, session_id),
                current_password="wrong-password",
                correlation_id=uuid4(),
            )
        )

    assert writer.session_id is None


@pytest.mark.asyncio
async def test_reauthentication_runs_dummy_hash_for_missing_password_identity() -> None:
    actor_id, session_id = uuid4(), uuid4()
    hasher = PasswordHasher(matches=False)
    writer = SessionReauthenticationWriter()
    use_case = ReauthenticateBrowserSession(
        identifiers=Identifiers(uuid4()),
        clock=FixedClock(datetime(2026, 8, 22, tzinfo=UTC)),
        user_statuses=UserStatuses(),
        credentials=Credentials(None),
        password_hasher=hasher,
        sessions=writer,
    )

    with pytest.raises(BrowserSessionReauthenticationRejectedError):
        await use_case.execute(
            ReauthenticateBrowserSessionCommand(
                principal=principal(actor_id, session_id),
                current_password="password",
                correlation_id=uuid4(),
            )
        )

    assert hasher.hash_calls == 1
    assert writer.session_id is None
