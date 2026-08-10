"""Revoke one first-party Console browser session with a mandatory audit fact."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    AuthSessionRevoker,
    Clock,
    IdentifierGenerator,
)
from muxivo_console.domain.audit import AuditEvent


@dataclass(frozen=True, slots=True)
class RevokeBrowserSessionCommand:
    actor_id: UUID
    session_id: UUID
    correlation_id: UUID


@dataclass(slots=True)
class RevokeBrowserSession:
    identifiers: IdentifierGenerator
    clock: Clock
    sessions: AuthSessionRevoker

    async def execute(self, command: RevokeBrowserSessionCommand) -> bool:
        """Revoke the bound session; repeated/concurrent revocation is safely idempotent."""
        return await self.sessions.revoke(
            session_id=command.session_id,
            user_id=command.actor_id,
            revoked_at=self.clock.now(),
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=None,
                action="auth.session_revoked",
                resource_type="auth_session",
                resource_id=str(command.session_id),
                result="succeeded",
            ),
        )
