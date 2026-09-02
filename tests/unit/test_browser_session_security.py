from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_browser_sessions import (
    BrowserSessionListRejectedError,
    ListBrowserSessions,
    ListBrowserSessionsCommand,
)
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.application.revoke_all_browser_sessions import (
    BrowserSessionBulkRevocationRejectedError,
    RevokeAllBrowserSessions,
    RevokeAllBrowserSessionsCommand,
)
from muxivo_console.application.revoke_browser_session import RevokeBrowserSession
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel


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

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


class SessionListingReader:
    def __init__(self, sessions: tuple[AuthSession, ...]) -> None:
        self.sessions = sessions
        self.active_at: datetime | None = None

    async def list_active_for_user(self, *, user_id: UUID, active_at) -> tuple[AuthSession, ...]:
        self.active_at = active_at
        return self.sessions


class BulkRevoker:
    def __init__(self, count: int) -> None:
        self.count = count
        self.audit_event: AuditEvent | None = None
        self.revoked_at: datetime | None = None

    async def revoke_all_for_user(
        self, *, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> int:
        self.revoked_at = revoked_at
        self.audit_event = audit_event
        return self.count


class CurrentSessionRevoker:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.audit_event: AuditEvent | None = None
        self.revoked_at: datetime | None = None
        self.session_id: UUID | None = None
        self.user_id: UUID | None = None

    async def revoke(
        self, *, session_id: UUID, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> bool:
        self.session_id = session_id
        self.user_id = user_id
        self.revoked_at = revoked_at
        self.audit_event = audit_event
        return self.result


def session(user_id: UUID, *, session_id: UUID | None = None) -> AuthSession:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    return AuthSession(
        id=session_id or uuid4(),
        user_id=user_id,
        token_hash="a" * 64,
        expires_at=now + timedelta(days=14),
        assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
        authenticated_at=now,
        last_seen_at=now + timedelta(minutes=5),
        ip_hash="b" * 64,
        user_agent_hash="c" * 64,
    )


def principal(
    user_id: UUID,
    session_id: UUID,
    *,
    assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.RECENT_AUTHENTICATION,
    authenticated_at: datetime | None = datetime(2026, 8, 10, tzinfo=UTC),
) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(
        user_id=user_id,
        session_id=session_id,
        assurance_level=assurance_level,
        authenticated_at=authenticated_at,
    )


@pytest.mark.asyncio
async def test_active_user_lists_sessions_and_marks_current_session() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    actor_id = uuid4()
    current_session_id = uuid4()
    reader = SessionListingReader(
        (
            session(actor_id, session_id=current_session_id),
            session(actor_id),
        )
    )
    use_case = ListBrowserSessions(
        clock=FixedClock(now),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        sessions=reader,
    )

    sessions = await use_case.execute(
        ListBrowserSessionsCommand(
            actor_id=actor_id,
            current_session_id=current_session_id,
            correlation_id=uuid4(),
        )
    )

    assert reader.active_at == now
    assert len(sessions) == 2
    assert sessions[0].is_current is True
    assert sessions[1].is_current is False


@pytest.mark.asyncio
async def test_revoke_current_session_records_security_audit_event() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    audit_id = uuid4()
    actor_id = uuid4()
    current_session_id = uuid4()
    correlation_id = uuid4()
    revoker = CurrentSessionRevoker()
    use_case = RevokeBrowserSession(
        identifiers=SequenceIdentifiers([audit_id]),
        clock=FixedClock(now),
        sessions=revoker,
    )

    await use_case.execute(
        user_id=actor_id,
        session_id=current_session_id,
        correlation_id=correlation_id,
    )

    assert revoker.session_id == current_session_id
    assert revoker.user_id == actor_id
    assert revoker.revoked_at == now
    assert revoker.audit_event is not None
    assert revoker.audit_event.id == audit_id
    assert revoker.audit_event.correlation_id == correlation_id
    assert revoker.audit_event.action == "auth.session_revoked"
    assert revoker.audit_event.resource_id == str(current_session_id)


@pytest.mark.asyncio
async def test_inactive_user_cannot_list_sessions() -> None:
    use_case = ListBrowserSessions(
        clock=FixedClock(datetime(2026, 8, 10, tzinfo=UTC)),
        user_statuses=UserStatuses(UserStatus.SUSPENDED),
        sessions=SessionListingReader(()),
    )

    with pytest.raises(BrowserSessionListRejectedError):
        await use_case.execute(
            ListBrowserSessionsCommand(
                actor_id=uuid4(),
                current_session_id=uuid4(),
                correlation_id=uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_revoke_all_sessions_records_bulk_audit_event() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    audit_id = uuid4()
    actor_id = uuid4()
    current_session_id = uuid4()
    revoker = BulkRevoker(3)
    use_case = RevokeAllBrowserSessions(
        identifiers=SequenceIdentifiers([audit_id]),
        clock=FixedClock(now),
        sessions=revoker,
        recent_authentication=RequireRecentAuthentication(clock=FixedClock(now)),
    )

    revoked_count = await use_case.execute(
        RevokeAllBrowserSessionsCommand(
            principal=principal(actor_id, current_session_id),
            correlation_id=uuid4(),
        )
    )

    assert revoked_count == 3
    assert revoker.revoked_at == now
    assert revoker.audit_event is not None
    assert revoker.audit_event.id == audit_id
    assert revoker.audit_event.action == "auth.sessions_revoked"
    assert revoker.audit_event.resource_id == str(current_session_id)


@pytest.mark.asyncio
async def test_revoke_all_sessions_fails_closed_when_nothing_was_revoked() -> None:
    use_case = RevokeAllBrowserSessions(
        identifiers=SequenceIdentifiers([uuid4()]),
        clock=FixedClock(datetime(2026, 8, 10, tzinfo=UTC)),
        sessions=BulkRevoker(0),
        recent_authentication=RequireRecentAuthentication(
            clock=FixedClock(datetime(2026, 8, 10, tzinfo=UTC))
        ),
    )

    with pytest.raises(BrowserSessionBulkRevocationRejectedError):
        await use_case.execute(
            RevokeAllBrowserSessionsCommand(
                principal=principal(uuid4(), uuid4()),
                correlation_id=uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_revoke_all_sessions_requires_recent_authentication() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    revoker = BulkRevoker(3)
    now = datetime(2026, 8, 10, tzinfo=UTC)
    use_case = RevokeAllBrowserSessions(
        identifiers=SequenceIdentifiers([uuid4()]),
        clock=FixedClock(now),
        sessions=revoker,
        recent_authentication=RequireRecentAuthentication(clock=FixedClock(now)),
    )

    with pytest.raises(RecentAuthenticationRequiredError):
        await use_case.execute(
            RevokeAllBrowserSessionsCommand(
                principal=principal(
                    actor_id,
                    session_id,
                    assurance_level=SessionAssuranceLevel.PASSWORD,
                    authenticated_at=datetime(2026, 8, 9, tzinfo=UTC),
                ),
                correlation_id=uuid4(),
            )
        )

    assert revoker.audit_event is None
