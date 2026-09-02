"""Compatibility exports for provider OAuth login initiation."""

from muxivo_console.application.begin_oauth_login_use_case import BeginOAuthLogin
from muxivo_console.application.oauth_login_start_error import OAuthLoginStartRejectedError
from muxivo_console.application.started_oauth_login import StartedOAuthLogin

__all__ = ["BeginOAuthLogin", "OAuthLoginStartRejectedError", "StartedOAuthLogin"]
