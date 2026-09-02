"""Discord OAuth configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscordOAuthSettings:
    """Validated credentials and callback for the Discord OAuth client."""

    client_id: str
    client_secret: str
    redirect_uri: str
