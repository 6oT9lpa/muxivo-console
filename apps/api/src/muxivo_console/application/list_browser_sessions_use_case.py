"""Use case for listing active browser sessions."""

import logging
from dataclasses import dataclass

from muxivo_console.application.browser_session_list_error import BrowserSessionListRejectedError
from muxivo_console.application.browser_session_security_view import BrowserSessionSecurityView
from muxivo_console.application.list_browser_sessions_command import ListBrowserSessionsCommand
from muxivo_console.application.ports import AuthSessionListingReader, Clock, UserStatusReader
from muxivo_console.domain.identity import UserStatus

logger = logging.getLogger("muxivo_console.application.list_browser_sessions")


@dataclass(slots=True)
class ListBrowserSessions:
    """Read active sessions for an active Console user."""

    clock: Clock
    user_statuses: UserStatusReader
    sessions: AuthSessionListingReader

    async def execute(
        self, command: ListBrowserSessionsCommand
    ) -> tuple[BrowserSessionSecurityView, ...]:
        logger.info(
            "auth.sessions.list.started",
            extra={
                "actor_id": str(command.actor_id),
                "current_session_id": str(command.current_session_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "auth.sessions.list.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionListRejectedError("Access denied.")
        sessions = tuple(
            await self.sessions.list_active_for_user(
                user_id=command.actor_id,
                active_at=self.clock.now(),
            )
        )
        views = tuple(
            BrowserSessionSecurityView(
                session=session,
                is_current=session.id == command.current_session_id,
            )
            for session in sessions
        )
        logger.info(
            "auth.sessions.list.completed",
            extra={
                "actor_id": str(command.actor_id),
                "session_count": len(views),
                "correlation_id": str(command.correlation_id),
            },
        )
        return views
