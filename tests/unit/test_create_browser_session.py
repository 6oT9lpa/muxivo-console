from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.create_browser_session import (
    CreateBrowserSession,
    CreateBrowserSessionCommand,
    SessionCreationRejectedError,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession


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


class TokenIssuer:
    def issue(self) -> str:
        return "opaque-browser-token"


class TokenHasher:
    def hash(self, raw_token: str) -> str:
        assert raw_token == "opaque-browser-token"
        return "a" * 64


class SessionWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.session: AuthSession | None = None
        self.audit_event: AuditEvent | None = None

    async def create(self, *, session: AuthSession, audit_event: AuditEvent) -> bool:
        self.session = session
        self.audit_event = audit_event
        return self.result


def command(user_id: UUID) -> CreateBrowserSessionCommand:
    return CreateBrowserSessionCommand(user_id=user_id, correlation_id=uuid4())


@pytest.mark.asyncio
async def test_active_user_receives_raw_token_once_while_storage_receives_only_hash() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    session_id, audit_event_id, user_id = uuid4(), uuid4(), uuid4()
    writer = SessionWriter()
    use_case = CreateBrowserSession(
        identifiers=SequenceIdentifiers([session_id, audit_event_id]),
        clock=FixedClock(now),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        sessions=writer,
    )

    issued = await use_case.execute(command(user_id))

    assert issued.raw_token == "opaque-browser-token"
    assert "opaque-browser-token" not in repr(issued)
    assert writer.session.token_hash == "a" * 64
    assert writer.session.expires_at == now + timedelta(days=14)
    assert writer.audit_event.action == "auth.session_created"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", (None, UserStatus.PENDING_VERIFICATION, UserStatus.SUSPENDED))
async def test_inactive_user_cannot_create_browser_session(status: UserStatus | None) -> None:
    writer = SessionWriter()
    use_case = CreateBrowserSession(
        identifiers=SequenceIdentifiers([uuid4(), uuid4()]),
        clock=FixedClock(datetime(2026, 8, 9, tzinfo=UTC)),
        user_statuses=UserStatuses(status),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        sessions=writer,
    )

    with pytest.raises(SessionCreationRejectedError):
        await use_case.execute(command(uuid4()))

    assert writer.session is None
