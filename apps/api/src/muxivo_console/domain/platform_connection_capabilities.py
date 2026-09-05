"""Platform capability keys persisted as non-secret connection metadata."""

from __future__ import annotations

from muxivo_console.domain.activity import Platform

_CAPABILITY_KEYS: dict[Platform, tuple[str, ...]] = {
    Platform.DISCORD: (
        "discord.guild.read",
        "discord.guild.manage",
    ),
    Platform.TWITCH: (
        "twitch.channel.read",
        "twitch.channel.manage",
    ),
    Platform.TELEGRAM: (
        "telegram.chat.read",
        "telegram.chat.manage",
    ),
}


def capability_keys_for_platform(platform: Platform) -> tuple[str, ...]:
    """Return the stable capability keys requested by a platform connection."""
    return _CAPABILITY_KEYS.get(platform, ())
