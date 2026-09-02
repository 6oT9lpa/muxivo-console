"""Twitch OAuth configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TwitchOAuthSettings:
    """Validated credentials and callback for the Twitch OAuth client."""

    client_id: str
    client_secret: str
    redirect_uri: str
