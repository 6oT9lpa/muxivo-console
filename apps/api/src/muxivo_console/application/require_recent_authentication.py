"""Guard sensitive Console commands with a bounded, server-side reauthentication window."""

from dataclasses import dataclass
from datetime import timedelta

from muxivo_console.application.ports import Clock
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.sessions import SessionAssuranceLevel


class RecentAuthenticationRequiredError(PermissionError):
    """Raised when the caller must reauthenticate before a sensitive command."""


@dataclass(slots=True)
class RequireRecentAuthentication:
    clock: Clock
    maximum_age: timedelta = timedelta(minutes=15)

    def check(self, principal: BrowserSessionPrincipal) -> None:
        authenticated_at = principal.authenticated_at
        now = self.clock.now()
        if (
            principal.assurance_level is not SessionAssuranceLevel.RECENT_AUTHENTICATION
            or authenticated_at is None
            or authenticated_at > now
            or now - authenticated_at > self.maximum_age
        ):
            raise RecentAuthenticationRequiredError(
                "Recent authentication is required for this operation."
            )
