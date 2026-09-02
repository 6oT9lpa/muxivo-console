"""Command for revoking all browser sessions."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal


@dataclass(frozen=True, slots=True)
class RevokeAllBrowserSessionsCommand:
    """Identify the reauthenticated principal requesting bulk revocation."""

    principal: BrowserSessionPrincipal
    correlation_id: UUID
