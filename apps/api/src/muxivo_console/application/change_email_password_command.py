"""Command for changing a first-party password."""

from dataclasses import dataclass, field
from uuid import UUID

from muxivo_console.application.browser_session_principal import BrowserSessionPrincipal


@dataclass(frozen=True, slots=True)
class ChangeEmailPasswordCommand:
    """Carry password-change input without exposing passwords in diagnostics."""

    principal: BrowserSessionPrincipal
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
    correlation_id: UUID
