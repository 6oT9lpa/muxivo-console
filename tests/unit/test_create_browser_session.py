import logging
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
    def __init__(self) -> None:
        self.tokens = iter(("opaque-browser-token", "opaque-csrf-token"))

    def issue(self) -> str:
        return next(self.tokens)


class TokenHasher:
    def hash(self, raw_token: str) -> str:
        assert raw_token == "opaque-browser-token"
        return "a" * 64


class FingerprintHasher:
    def __init__(self) -> None:
        self.ip_addresses: list[str] = []
        self.user_agents: list[str] = []

    def hash_ip_address(self, ip_address: str) -> str:
        self.ip_addresses.append(ip_address)
        return "b" * 64

    def hash_user_agent(self, user_agent: str) -> str:
        self.user_agents.append(user_agent)
        return "c" * 64


class SessionWriter:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.session: AuthSession | None = None
        self.audit_event: AuditEvent | None = None

    async def create(self, *, session: AuthSession, audit_event: AuditEvent) -> bool:
        self.session = session
        self.audit_event = audit_event
        return self.result


def command(
    user_id: UUID,
    *,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> CreateBrowserSessionCommand:
    return CreateBrowserSessionCommand(
        user_id=user_id,
        correlation_id=uuid4(),
        client_ip=client_ip,
        user_agent=user_agent,
    )


@pytest.mark.asyncio
async def test_active_user_receives_raw_token_once_while_storage_receives_only_hash(
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="muxivo_console.application.create_browser_session")
    now = datetime(2026, 8, 9, tzinfo=UTC)
    session_id, audit_event_id, user_id = uuid4(), uuid4(), uuid4()
    writer = SessionWriter()
    fingerprint_hasher = FingerprintHasher()
    use_case = CreateBrowserSession(
        identifiers=SequenceIdentifiers([session_id, audit_event_id]),
        clock=FixedClock(now),
        user_statuses=UserStatuses(UserStatus.ACTIVE),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        fingerprint_hasher=fingerprint_hasher,
        sessions=writer,
    )

    issued = await use_case.execute(
        command(
            user_id,
            client_ip=" 203.0.113.10 ",
            user_agent=" Mozilla/5.0 ",
        )
    )

    assert issued.raw_token == "opaque-browser-token"
    assert issued.raw_csrf_token == "opaque-csrf-token"
    assert "opaque-browser-token" not in repr(issued)
    assert "opaque-csrf-token" not in repr(issued)
    assert writer.session.token_hash == "a" * 64
    assert writer.session.expires_at == now + timedelta(days=14)
    assert writer.session.ip_hash == "b" * 64
    assert writer.session.user_agent_hash == "c" * 64
    assert fingerprint_hasher.ip_addresses == ["203.0.113.10"]
    assert fingerprint_hasher.user_agents == ["Mozilla/5.0"]
    assert writer.audit_event.action == "auth.session_created"
    event_names = [record.message for record in caplog.records]
    assert event_names == [
        "auth.session.create.started",
        "auth.session.create.credentials_issued",
        "auth.session.create.completed",
    ]
    assert "opaque-browser-token" not in caplog.text
    assert "203.0.113.10" not in caplog.text
    assert "Mozilla/5.0" not in caplog.text


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
        fingerprint_hasher=FingerprintHasher(),
        sessions=writer,
    )

    with pytest.raises(SessionCreationRejectedError):
        await use_case.execute(command(uuid4()))

    assert writer.session is None
