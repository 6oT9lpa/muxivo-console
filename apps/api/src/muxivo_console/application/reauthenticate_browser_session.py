"""Refresh recent-authentication assurance for the current browser session."""

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    BrowserSessionReauthenticationWriter,
    Clock,
    IdentifierGenerator,
    PasswordCredentialReader,
    PasswordHasher,
    UserStatusReader,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus

logger = logging.getLogger(__name__)


class BrowserSessionReauthenticationRejectedError(PermissionError):
    """Publicly safe failure for current-session reauthentication."""


@dataclass(frozen=True, slots=True)
class ReauthenticateBrowserSessionCommand:
    principal: BrowserSessionPrincipal
    current_password: str
    correlation_id: UUID


@dataclass(slots=True)
class ReauthenticateBrowserSession:
    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    credentials: PasswordCredentialReader
    password_hasher: PasswordHasher
    sessions: BrowserSessionReauthenticationWriter

    async def execute(self, command: ReauthenticateBrowserSessionCommand) -> None:
        actor_id = command.principal.user_id
        logger.info(
            "session.reauthentication.started",
            extra={
                "actor_id": str(actor_id),
                "session_id": str(command.principal.session_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        if await self.user_statuses.get_status(user_id=actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "session.reauthentication.denied_inactive_user",
                extra={
                    "actor_id": str(actor_id),
                    "session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionReauthenticationRejectedError("Reauthentication failed.")

        credential = await self.credentials.find_for_user(user_id=actor_id)
        if credential is None:
            self.password_hasher.hash(command.current_password)
            logger.warning(
                "session.reauthentication.missing_password_identity",
                extra={
                    "actor_id": str(actor_id),
                    "session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionReauthenticationRejectedError("Reauthentication failed.")
        if not self.password_hasher.verify(credential.password_hash, command.current_password):
            logger.warning(
                "session.reauthentication.denied_current_password",
                extra={
                    "actor_id": str(actor_id),
                    "session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionReauthenticationRejectedError("Reauthentication failed.")

        authenticated_at = self.clock.now()
        reauthenticated = await self.sessions.reauthenticate(
            session_id=command.principal.session_id,
            user_id=actor_id,
            authenticated_at=authenticated_at,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=actor_id,
                organization_id=None,
                action="auth.session_reauthenticated",
                resource_type="auth_session",
                resource_id=str(command.principal.session_id),
                result="succeeded",
            ),
        )
        if not reauthenticated:
            logger.warning(
                "session.reauthentication.conflict",
                extra={
                    "actor_id": str(actor_id),
                    "session_id": str(command.principal.session_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise BrowserSessionReauthenticationRejectedError("Reauthentication failed.")
        logger.info(
            "session.reauthentication.completed",
            extra={
                "actor_id": str(actor_id),
                "session_id": str(command.principal.session_id),
                "correlation_id": str(command.correlation_id),
            },
        )
