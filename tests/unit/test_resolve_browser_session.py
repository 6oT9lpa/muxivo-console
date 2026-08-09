from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.resolve_browser_session import ResolveBrowserSession
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class TokenHasher:
    def hash(self, raw_token: str) -> str:
        return f"hashed:{raw_token}".ljust(64, "_")


class Sessions:
    def __init__(self, session: AuthSession | None) -> None:
        self.session = session
        self.token_hash: str | None = None

    async def find_by_token_hash(self, *, token_hash: str) -> AuthSession | None:
        self.token_hash = token_hash
        return self.session


class UserStatuses:
    def __init__(self, status: UserStatus | None) -> None:
        self.status = status

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        return self.status


def session(*, expires_at: datetime, revoked_at: datetime | None = None) -> AuthSession:
    return AuthSession(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="a" * 64,
        expires_at=expires_at,
        revoked_at=revoked_at,
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )


@pytest.mark.asyncio
async def test_resolves_only_active_session_for_active_user() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    stored = session(expires_at=now + timedelta(hours=1))
    sessions = Sessions(stored)
    resolver = ResolveBrowserSession(
        FixedClock(now), TokenHasher(), sessions, UserStatuses(UserStatus.ACTIVE)
    )

    principal = await resolver.execute("opaque-token")

    assert principal.user_id == stored.user_id
    assert principal.session_id == stored.id
    assert sessions.token_hash == "hashed:opaque-token".ljust(64, "_")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expires_at", "revoked_at", "user_status"),
    (
        (datetime(2026, 8, 9, tzinfo=UTC), None, UserStatus.ACTIVE),
        (datetime(2026, 8, 10, tzinfo=UTC), datetime(2026, 8, 9, tzinfo=UTC), UserStatus.ACTIVE),
        (datetime(2026, 8, 10, tzinfo=UTC), None, UserStatus.SUSPENDED),
        (datetime(2026, 8, 10, tzinfo=UTC), None, None),
    ),
)
async def test_fails_closed_for_expired_revoked_or_inactive_principals(
    expires_at: datetime, revoked_at: datetime | None, user_status: UserStatus | None
) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    resolver = ResolveBrowserSession(
        FixedClock(now),
        TokenHasher(),
        Sessions(session(expires_at=expires_at, revoked_at=revoked_at)),
        UserStatuses(user_status),
    )

    assert await resolver.execute("opaque-token") is None


@pytest.mark.asyncio
async def test_rejects_empty_whitespace_and_unbounded_tokens_before_lookup() -> None:
    sessions = Sessions(None)
    resolver = ResolveBrowserSession(
        FixedClock(datetime(2026, 8, 9, tzinfo=UTC)),
        TokenHasher(),
        sessions,
        UserStatuses(UserStatus.ACTIVE),
    )

    assert await resolver.execute("") is None
    assert await resolver.execute("a b") is None
    assert await resolver.execute("a" * 4097) is None
    assert sessions.token_hash is None
