"""Resolve an opaque browser token to a fail-closed Console principal."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from muxivo_console.application.browser_session_principal import BrowserSessionPrincipal
from muxivo_console.application.ports import (
    AuthSessionLastSeenUpdater,
    AuthSessionReader,
    Clock,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession

logger = logging.getLogger("muxivo_console.application.resolve_browser_session")


@dataclass(slots=True)
class ResolveBrowserSession:
    """Resolve, validate and optionally touch an opaque browser session."""

    clock: Clock
    token_hasher: SessionTokenHasher
    sessions: AuthSessionReader
    user_statuses: UserStatusReader
    last_seen_updater: AuthSessionLastSeenUpdater | None = None
    last_seen_update_interval: timedelta = timedelta(minutes=5)

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        logger.info("auth.session.resolve.started", extra={"has_token": bool(raw_token)})
        if not _is_usable_token(raw_token):
            logger.warning("auth.session.resolve.rejected_token_shape")
            return None
        session = await self.sessions.find_by_token_hash(
            token_hash=self.token_hasher.hash(raw_token)
        )
        now = self.clock.now()
        if session is None or not session.is_active_at(now):
            logger.warning("auth.session.resolve.rejected_session")
            return None
        if await self.user_statuses.get_status(user_id=session.user_id) is not UserStatus.ACTIVE:
            logger.warning(
                "auth.session.resolve.rejected_inactive_user",
                extra={"user_id": str(session.user_id), "session_id": str(session.id)},
            )
            return None
        await self._touch_last_seen(session, now)
        principal = BrowserSessionPrincipal(
            user_id=session.user_id,
            session_id=session.id,
            assurance_level=session.assurance_level,
            authenticated_at=session.authenticated_at,
        )
        logger.info(
            "auth.session.resolve.completed",
            extra={"user_id": str(session.user_id), "session_id": str(session.id)},
        )
        return principal

    async def _touch_last_seen(self, session: AuthSession, now: datetime) -> None:
        if self.last_seen_updater is None or not _last_seen_requires_update(
            session.last_seen_at,
            now,
            self.last_seen_update_interval,
        ):
            return
        try:
            updated = await self.last_seen_updater.touch_last_seen(
                session_id=session.id,
                user_id=session.user_id,
                last_seen_at=now,
            )
        except Exception as error:
            logger.warning(
                "auth.session.last_seen_update_failed",
                extra={
                    "session_id": str(session.id),
                    "user_id": str(session.user_id),
                    "error_type": type(error).__name__,
                },
            )
            return
        logger.info(
            "auth.session.last_seen_updated" if updated else "auth.session.last_seen_skipped",
            extra={
                "session_id": str(session.id),
                "user_id": str(session.user_id),
                "reason": "persisted" if updated else "session_changed",
            },
        )


def _is_usable_token(token: str) -> bool:
    if not token or len(token) > 4096:
        return False
    return not any(character.isspace() for character in token)


def _last_seen_requires_update(
    last_seen_at: datetime | None,
    now: datetime,
    interval: timedelta,
) -> bool:
    if interval <= timedelta(0):
        raise ValueError("Last-seen update interval must be positive.")
    return last_seen_at is None or now - last_seen_at >= interval
