"""Resolve an opaque browser token to a fail-closed Console principal."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from muxivo_console.application.ports import (
    AuthSessionReader,
    Clock,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.sessions import SessionAssuranceLevel


@dataclass(frozen=True, slots=True)
class BrowserSessionPrincipal:
    user_id: UUID
    session_id: UUID
    assurance_level: SessionAssuranceLevel
    authenticated_at: datetime | None = None


@dataclass(slots=True)
class ResolveBrowserSession:
    clock: Clock
    token_hasher: SessionTokenHasher
    sessions: AuthSessionReader
    user_statuses: UserStatusReader

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        if (
            not raw_token
            or len(raw_token) > 4096
            or any(character.isspace() for character in raw_token)
        ):
            return None
        session = await self.sessions.find_by_token_hash(
            token_hash=self.token_hasher.hash(raw_token)
        )
        if session is None or not session.is_active_at(self.clock.now()):
            return None
        if await self.user_statuses.get_status(user_id=session.user_id) is not UserStatus.ACTIVE:
            return None
        return BrowserSessionPrincipal(
            user_id=session.user_id,
            session_id=session.id,
            assurance_level=session.assurance_level,
            authenticated_at=session.authenticated_at,
        )
