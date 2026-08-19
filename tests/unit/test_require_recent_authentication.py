from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from muxivo_console.application.require_recent_authentication import (
    RecentAuthenticationRequiredError,
    RequireRecentAuthentication,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.now_value = now

    def now(self) -> datetime:
        return self.now_value


def principal(
    *, level: SessionAssuranceLevel, authenticated_at: datetime | None
) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(uuid4(), uuid4(), level, authenticated_at)


def test_allows_a_recently_reauthenticated_browser_session() -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)

    RequireRecentAuthentication(FixedClock(now)).check(
        principal(
            level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
            authenticated_at=now - timedelta(minutes=14),
        )
    )


@pytest.mark.parametrize(
    "level,age",
    [
        (SessionAssuranceLevel.PASSWORD, timedelta(minutes=1)),
        (SessionAssuranceLevel.RECENT_AUTHENTICATION, timedelta(minutes=16)),
        (SessionAssuranceLevel.RECENT_AUTHENTICATION, None),
    ],
)
def test_rejects_non_recent_expired_or_legacy_sessions(level, age) -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    authenticated_at = now - age if age is not None else None

    with pytest.raises(RecentAuthenticationRequiredError):
        RequireRecentAuthentication(FixedClock(now)).check(
            principal(level=level, authenticated_at=authenticated_at)
        )
