"""Use case for creating an opaque browser session."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from muxivo_console.application.create_browser_session_command import CreateBrowserSessionCommand
from muxivo_console.application.issued_browser_session import IssuedBrowserSession
from muxivo_console.application.ports import (
    AuthSessionWriter,
    Clock,
    IdentifierGenerator,
    OpaqueSessionTokenIssuer,
    SessionFingerprintHasher,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.application.session_creation_error import SessionCreationRejectedError
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import AuthSession

logger = logging.getLogger("muxivo_console.application.create_browser_session")


@dataclass(slots=True)
class CreateBrowserSession:
    """Issue and persist a session only for an active Console user."""

    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    fingerprint_hasher: SessionFingerprintHasher
    sessions: AuthSessionWriter
    lifetime: timedelta = timedelta(days=14)

    async def execute(self, command: CreateBrowserSessionCommand) -> IssuedBrowserSession:
        logger.info(
            "auth.session.create.started",
            extra={
                "user_id": str(command.user_id),
                "correlation_id": str(command.correlation_id),
                "assurance_level": command.assurance_level.value,
                "has_client_ip": bool(command.client_ip),
                "has_user_agent": bool(command.user_agent),
            },
        )
        if await self.user_statuses.get_status(user_id=command.user_id) is not UserStatus.ACTIVE:
            logger.warning(
                "auth.session.create.denied",
                extra={
                    "user_id": str(command.user_id),
                    "correlation_id": str(command.correlation_id),
                    "reason": "inactive_user",
                },
            )
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
            last_seen_at=now,
            ip_hash=_fingerprint_ip(self.fingerprint_hasher, command.client_ip),
            user_agent_hash=_fingerprint_user_agent(self.fingerprint_hasher, command.user_agent),
        )
        logger.info(
            "auth.session.create.credentials_issued",
            extra={
                "user_id": str(command.user_id),
                "session_id": str(session.id),
                "correlation_id": str(command.correlation_id),
                "has_ip_fingerprint": session.ip_hash is not None,
                "has_user_agent_fingerprint": session.user_agent_hash is not None,
            },
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
            logger.warning(
                "auth.session.create.persistence_failed",
                extra={
                    "user_id": str(command.user_id),
                    "session_id": str(session.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise SessionCreationRejectedError("The session could not be created.")
        logger.info(
            "auth.session.create.completed",
            extra={
                "user_id": str(command.user_id),
                "session_id": str(session.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return IssuedBrowserSession(
            id=session.id,
            raw_token=raw_token,
            raw_csrf_token=raw_csrf_token,
            expires_at=session.expires_at,
            assurance_level=session.assurance_level,
        )


def _fingerprint_ip(hasher: SessionFingerprintHasher, ip_address: str | None) -> str | None:
    value = (ip_address or "").strip()
    return hasher.hash_ip_address(value) if value else None


def _fingerprint_user_agent(hasher: SessionFingerprintHasher, user_agent: str | None) -> str | None:
    value = (user_agent or "").strip()
    return hasher.hash_user_agent(value) if value else None
