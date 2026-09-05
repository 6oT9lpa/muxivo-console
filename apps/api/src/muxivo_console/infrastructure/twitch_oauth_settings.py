"""Twitch OAuth configuration value object."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TwitchOAuthSettings:
    """Validated credentials and callback for the Twitch OAuth client."""

    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
