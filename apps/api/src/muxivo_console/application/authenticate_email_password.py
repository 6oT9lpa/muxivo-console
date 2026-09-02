"""Compatibility exports for first-party e-mail/password authentication."""

from muxivo_console.application.authenticate_email_password_command import (
    AuthenticateEmailPasswordCommand,
)
from muxivo_console.application.authenticate_email_password_use_case import (
    AuthenticateEmailPassword,
)
from muxivo_console.application.authentication_rejected_error import (
    AuthenticationRejectedError,
)

__all__ = [
    "AuthenticateEmailPassword",
    "AuthenticateEmailPasswordCommand",
    "AuthenticationRejectedError",
]
