"""Use case for revoking every active browser session for one user."""

import logging
from dataclasses import dataclass

from muxivo_console.application.browser_session_bulk_revocation_error import (
    BrowserSessionBulkRevocationRejectedError,
)
from muxivo_console.application.ports import AuthSessionBulkRevoker, Clock, IdentifierGenerator
from muxivo_console.application.require_recent_authentication import RequireRecentAuthentication
from muxivo_console.application.revoke_all_browser_sessions_command import (
    RevokeAllBrowserSessionsCommand,
)
from muxivo_console.domain.audit import AuditEvent

logger = logging.getLogger("muxivo_console.application.revoke_all_browser_sessions")


@dataclass(slots=True)
class RevokeAllBrowserSessions:
    """Revoke all active sessions after a recent-authentication check."""

    identifiers: IdentifierGenerator
    clock: Clock
    sessions: AuthSessionBulkRevoker
    recent_authentication: RequireRecentAuthentication

    async def execute(self, command: RevokeAllBrowserSessionsCommand) -> int:
        self.recent_authentication.check(command.principal)
        logger.info(
            "auth.sessions.revoke_all.started",
            extra={
                "actor_id": str(command.principal.user_id),
                "current_session_id": str(command.principal.session_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        revoked_count = await self.sessions.revoke_all_for_user(
            user_id=command.principal.user_id,
            revoked_at=self.clock.now(),
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.principal.user_id,
                organization_id=None,
                action="auth.sessions_revoked",
                resource_type="auth_session",
                resource_id=str(command.principal.session_id),
                result="succeeded",
            ),
        )
        if revoked_count < 1:
            logger.warning(
                "auth.sessions.revoke_all.denied",
                extra={
                    "actor_id": str(command.principal.user_id),
                    "current_session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionBulkRevocationRejectedError("No active sessions were revoked.")
        logger.info(
            "auth.sessions.revoke_all.completed",
            extra={
                "actor_id": str(command.principal.user_id),
                "revoked_count": revoked_count,
                "correlation_id": str(command.correlation_id),
            },
        )
        return revoked_count
