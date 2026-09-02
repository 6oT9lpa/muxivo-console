"""Compatibility exports for first-party e-mail/password registration."""

from muxivo_console.application.register_email_password_command import RegisterEmailPasswordCommand
from muxivo_console.application.register_email_password_use_case import RegisterEmailPassword
from muxivo_console.application.registration_rejected_error import RegistrationRejectedError

__all__ = ["RegisterEmailPassword", "RegisterEmailPasswordCommand", "RegistrationRejectedError"]
