"""Create an opaque browser session for an already-authenticated active user."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from muxivo_console.application.ports import (
    AuthSessionWriter,
    Clock,
    IdentifierGenerator,
    OpaqueSessionTokenIssuer,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession, SessionAssuranceLevel


class SessionCreationRejectedError(PermissionError):
    """Raised when an inactive user attempts to create a Console browser session."""


@dataclass(frozen=True, slots=True)
class CreateBrowserSessionCommand:
    user_id: UUID
    correlation_id: UUID
    assurance_level: SessionAssuranceLevel = SessionAssuranceLevel.PASSWORD


@dataclass(frozen=True, slots=True)
class IssuedBrowserSession:
    """Raw browser credentials are excluded from repr/logging and returned once only."""

    id: UUID
    raw_token: str = field(repr=False)
    raw_csrf_token: str = field(repr=False)
    expires_at: datetime
    assurance_level: SessionAssuranceLevel


@dataclass(slots=True)
class CreateBrowserSession:
    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    sessions: AuthSessionWriter
    lifetime: timedelta = timedelta(days=14)

    async def execute(self, command: CreateBrowserSessionCommand) -> IssuedBrowserSession:
        if await self.user_statuses.get_status(user_id=command.user_id) is not UserStatus.ACTIVE:
            raise SessionCreationRejectedError("The user is not allowed to create a session.")
        now = self.clock.now()
        raw_token = self.token_issuer.issue()
        raw_csrf_token = self.token_issuer.issue()
        session = AuthSession(
            id=self.identifiers.new(),
            user_id=command.user_id,
            token_hash=self.token_hasher.hash(raw_token),
            expires_at=now + self.lifetime,
            assurance_level=command.assurance_level,
            authenticated_at=now,
        )
        created = await self.sessions.create(
            session=session,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.user_id,
                organization_id=None,
                action="auth.session_created",
                resource_type="auth_session",
                resource_id=str(session.id),
                result="succeeded",
            ),
        )
        if not created:
            raise SessionCreationRejectedError("The session could not be created.")
        return IssuedBrowserSession(
            id=session.id,
            raw_token=raw_token,
            raw_csrf_token=raw_csrf_token,
            expires_at=session.expires_at,
            assurance_level=session.assurance_level,
        )
