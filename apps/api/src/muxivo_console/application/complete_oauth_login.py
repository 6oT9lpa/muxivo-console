"""Compatibility exports for provider OAuth login completion."""

from muxivo_console.application.complete_oauth_login_use_case import CompleteOAuthLogin
from muxivo_console.application.oauth_login_completion_error import (
    OAuthLoginCompletionRejectedError,
)

__all__ = ["CompleteOAuthLogin", "OAuthLoginCompletionRejectedError"]
