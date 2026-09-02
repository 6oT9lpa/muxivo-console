"""Safe presentation wrapper for one browser session."""

from dataclasses import dataclass

from muxivo_console.domain.sessions import AuthSession


@dataclass(frozen=True, slots=True)
class BrowserSessionSecurityView:
    """Pair session metadata with whether it belongs to the current request."""

    session: AuthSession
    is_current: bool
