"""Google OAuth configuration value object."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class GoogleOAuthSettings:
    """Validated Google OAuth client credentials and callback URI."""

    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
