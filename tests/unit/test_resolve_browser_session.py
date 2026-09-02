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


class LastSeenUpdater:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.updates: list[tuple[UUID, UUID, datetime]] = []

    async def touch_last_seen(self, *, session_id: UUID, user_id: UUID, last_seen_at) -> bool:
        self.updates.append((session_id, user_id, last_seen_at))
        return self.result


class FailingLastSeenUpdater:
    async def touch_last_seen(self, **_: object) -> bool:
        raise RuntimeError("database unavailable")


def session(
    *,
    expires_at: datetime,
    revoked_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> AuthSession:
    return AuthSession(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="a" * 64,
        expires_at=expires_at,
        revoked_at=revoked_at,
        assurance_level=SessionAssuranceLevel.PASSWORD,
        last_seen_at=last_seen_at,
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
async def test_refreshes_stale_last_seen_without_touching_every_request() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    stored = session(
        expires_at=now + timedelta(hours=1),
        last_seen_at=now - timedelta(minutes=6),
    )
    updater = LastSeenUpdater()
    resolver = ResolveBrowserSession(
        FixedClock(now),
        TokenHasher(),
        Sessions(stored),
        UserStatuses(UserStatus.ACTIVE),
        last_seen_updater=updater,
    )

    principal = await resolver.execute("opaque-token")

    assert principal is not None
    assert updater.updates == [(stored.id, stored.user_id, now)]


@pytest.mark.asyncio
async def test_skips_recent_last_seen_update() -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    updater = LastSeenUpdater()
    resolver = ResolveBrowserSession(
        FixedClock(now),
        TokenHasher(),
        Sessions(
            session(
                expires_at=now + timedelta(hours=1),
                last_seen_at=now - timedelta(minutes=1),
            )
        ),
        UserStatuses(UserStatus.ACTIVE),
        last_seen_updater=updater,
    )

    assert await resolver.execute("opaque-token") is not None
    assert updater.updates == []


@pytest.mark.asyncio
async def test_last_seen_storage_failure_does_not_invalidate_a_valid_session(caplog) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    resolver = ResolveBrowserSession(
        FixedClock(now),
        TokenHasher(),
        Sessions(
            session(
                expires_at=now + timedelta(hours=1),
                last_seen_at=now - timedelta(minutes=6),
            )
        ),
        UserStatuses(UserStatus.ACTIVE),
        last_seen_updater=FailingLastSeenUpdater(),
    )
    caplog.set_level("WARNING", logger="muxivo_console.application.resolve_browser_session")

    assert await resolver.execute("opaque-token") is not None
    assert "auth.session.last_seen_update_failed" in caplog.text


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
