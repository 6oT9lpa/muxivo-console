"""Twitch Control API configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TwitchControlSettings:
    """Validated endpoint and signing key for Twitch Control API calls."""

    base_url: str
    signing_key: bytes
