"""Google OAuth configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleOAuthSettings:
    """Validated Google OAuth client credentials and callback URI."""

    client_id: str
    client_secret: str
    redirect_uri: str
