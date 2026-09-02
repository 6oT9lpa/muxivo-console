"""Compatibility exports for platform health."""

from muxivo_console.application.get_platform_health_use_case import GetPlatformHealth
from muxivo_console.application.platform_health_unavailable_error import (
    PlatformHealthUnavailableError,
)

__all__ = ["GetPlatformHealth", "PlatformHealthUnavailableError"]
