"""Browser session cookie policy value object."""

from dataclasses import dataclass

from muxivo_console.presentation.browser_security_constants import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
)


@dataclass(frozen=True, slots=True)
class BrowserSessionCookieSettings:
    """Browser-session cookie policy supplied only by the composition root."""

    session_name: str = SESSION_COOKIE_NAME
    csrf_name: str = CSRF_COOKIE_NAME
    secure: bool = True

    @classmethod
    def development(cls) -> "BrowserSessionCookieSettings":
        """Use local names because ``__Host-`` cookies must always be Secure."""
        return cls(
            session_name="muxivo_console_dev_session",
            csrf_name="muxivo_console_dev_csrf",
            secure=False,
        )
