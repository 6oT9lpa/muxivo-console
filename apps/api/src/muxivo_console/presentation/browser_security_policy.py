"""Browser-facing security policy value object."""

from dataclasses import dataclass

from muxivo_console.presentation.browser_security_constants import (
    DEFAULT_CONTENT_SECURITY_POLICY,
)


@dataclass(frozen=True, slots=True)
class BrowserSecurityPolicy:
    """Browser-facing security policy controlled by the composition root."""

    cors_allowed_origins: tuple[str, ...] = ()
    content_security_policy: str = DEFAULT_CONTENT_SECURITY_POLICY
    hsts_enabled: bool = True
    hsts_value: str = "max-age=31536000; includeSubDomains"

    @classmethod
    def development(cls, *, cors_allowed_origins: tuple[str, ...] = ()) -> "BrowserSecurityPolicy":
        return cls(cors_allowed_origins=cors_allowed_origins, hsts_enabled=False)
