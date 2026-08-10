from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.revoke_browser_session import (
    RevokeBrowserSession,
    RevokeBrowserSessionCommand,
)


class IdentifierGenerator:
    def __init__(self, identifier: UUID) -> None:
        self.identifier = identifier

    def new(self) -> UUID:
        return self.identifier


class Clock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


class SessionRevoker:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.arguments = None

    async def revoke(self, **kwargs) -> bool:
        self.arguments = kwargs
        return self.result


@pytest.mark.asyncio
async def test_revoke_browser_session_binds_actor_session_and_audit() -> None:
    actor_id = uuid4()
    session_id = uuid4()
    correlation_id = uuid4()
    audit_id = uuid4()
    now = datetime(2026, 8, 10, 13, 30, tzinfo=UTC)
    revoker = SessionRevoker()
    use_case = RevokeBrowserSession(
        identifiers=IdentifierGenerator(audit_id),
        clock=Clock(now),
        sessions=revoker,
    )

    revoked = await use_case.execute(
        RevokeBrowserSessionCommand(
            actor_id=actor_id,
            session_id=session_id,
            correlation_id=correlation_id,
        )
    )

    assert revoked is True
    assert revoker.arguments["session_id"] == session_id
    assert revoker.arguments["user_id"] == actor_id
    assert revoker.arguments["revoked_at"] == now
    audit = revoker.arguments["audit_event"]
    assert audit.id == audit_id
    assert audit.correlation_id == correlation_id
    assert audit.actor_id == actor_id
    assert audit.action == "auth.session_revoked"
    assert audit.resource_id == str(session_id)


@pytest.mark.asyncio
async def test_revoke_browser_session_is_idempotent_when_session_is_already_gone() -> None:
    revoker = SessionRevoker(result=False)
    use_case = RevokeBrowserSession(
        identifiers=IdentifierGenerator(uuid4()),
        clock=Clock(datetime(2026, 8, 10, 13, 30, tzinfo=UTC)),
        sessions=revoker,
    )

    revoked = await use_case.execute(
        RevokeBrowserSessionCommand(
            actor_id=uuid4(),
            session_id=uuid4(),
            correlation_id=uuid4(),
        )
    )

    assert revoked is False
