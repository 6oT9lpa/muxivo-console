"""Compatibility exports for recent-authentication policy."""

from muxivo_console.application.recent_authentication_error import RecentAuthenticationRequiredError
from muxivo_console.application.require_recent_authentication_use_case import (
    RequireRecentAuthentication,
)

__all__ = ["RecentAuthenticationRequiredError", "RequireRecentAuthentication"]
