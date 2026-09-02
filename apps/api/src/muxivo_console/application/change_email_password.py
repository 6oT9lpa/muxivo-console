"""Compatibility exports for first-party password changes."""

from muxivo_console.application.change_email_password_command import ChangeEmailPasswordCommand
from muxivo_console.application.change_email_password_use_case import ChangeEmailPassword
from muxivo_console.application.password_change_rejected_error import PasswordChangeRejectedError

__all__ = [
    "ChangeEmailPassword",
    "ChangeEmailPasswordCommand",
    "PasswordChangeRejectedError",
]
