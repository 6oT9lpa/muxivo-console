"""Platform-neutral representations of control-surface modules.

This model intentionally has no Discord identifiers, bot tokens, or transport
objects. A platform adapter translates its native concepts into these values.
"""

from dataclasses import dataclass
from enum import StrEnum


class Platform(StrEnum):
    DISCORD = "discord"
    TWITCH = "twitch"
    TELEGRAM = "telegram"


class ModuleCapability(StrEnum):
    VIEW = "view"
    MANAGE = "manage"


class ModuleStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    REQUIRES_REAUTHORIZATION = "requires_reauthorization"


@dataclass(frozen=True, slots=True)
class ControlModule:
    """A feature exposed by a platform service through its Control API."""

    key: str
    display_name: str
    platform: Platform
    capability: ModuleCapability
    status: ModuleStatus

    def __post_init__(self) -> None:
        if not self.key or "." not in self.key:
            raise ValueError("Module key must be a namespaced, non-empty identifier.")
        if not self.display_name.strip():
            raise ValueError("Module display name must not be blank.")
