"""Command for refreshing recent-authentication assurance."""

from dataclasses import dataclass, field
from uuid import UUID

from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal


@dataclass(frozen=True, slots=True)
class ReauthenticateBrowserSessionCommand:
    """Carry the current principal and password without exposing the password in repr."""

    principal: BrowserSessionPrincipal
    current_password: str = field(repr=False)
    correlation_id: UUID
