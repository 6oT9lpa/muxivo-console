"""Command for unlinking one authenticated login identity."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal


@dataclass(frozen=True, slots=True)
class UnlinkLoginIdentityCommand:
    """Identify the authenticated principal and identity to remove."""

    principal: BrowserSessionPrincipal
    identity_id: UUID
    correlation_id: UUID
