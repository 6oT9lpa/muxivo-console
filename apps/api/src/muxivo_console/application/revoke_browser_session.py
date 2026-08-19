"""Revoke the current first-party browser session on the server."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import AuthSessionRevoker, Clock, IdentifierGenerator
from muxivo_console.domain.audit import AuditEvent


@dataclass(slots=True)
class RevokeBrowserSession:
    identifiers: IdentifierGenerator
    clock: Clock
    sessions: AuthSessionRevoker

    async def execute(self, *, user_id: UUID, session_id: UUID, correlation_id: UUID) -> None:
        revoked = await self.sessions.revoke(
            session_id=session_id,
            user_id=user_id,
            revoked_at=self.clock.now(),
            audit_event=AuditEvent(
                id=self.identifiers.new(), correlation_id=correlation_id, actor_id=user_id,
                organization_id=None, action="auth.session_revoked", resource_type="auth_session",
                resource_id=str(session_id), result="succeeded",
            ),
        )
        if not revoked:
            raise PermissionError("Current session could not be revoked.")
