"""Out-of-band notification adapters for account security flows."""

import asyncio
import logging
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from urllib.parse import urlencode
from uuid import UUID

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings

logger = logging.getLogger(__name__)


class UndeliveredPasswordRecoveryNotifier:
    """Safe production placeholder until an email provider is configured.

    The notifier deliberately does not log the raw recovery token. A real
    deployment must replace this adapter with a mail/SMS provider before public
    launch.
    """

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        raw_token: str,
        expires_at,
        correlation_id: UUID,
    ) -> None:
        logger.warning(
            "password.recovery.delivery_unconfigured",
            extra={
                "user_id": str(user_id),
                "expires_at": expires_at.isoformat(),
                "correlation_id": str(correlation_id),
                "token_length": len(raw_token),
            },
        )


class SmtpPasswordRecoveryNotifier:
    """Deliver first-party password recovery messages via a configured SMTP relay."""

    def __init__(
        self,
        settings: SmtpPasswordRecoverySettings,
        *,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._settings = settings
        self._smtp_factory = smtp_factory
        self._timeout_seconds = timeout_seconds

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        raw_token: str,
        expires_at,
        correlation_id: UUID,
    ) -> None:
        logger.info(
            "password.recovery.delivery.started",
            extra={
                "user_id": str(user_id),
                "smtp_host": self._settings.host,
                "correlation_id": str(correlation_id),
            },
        )
        message = self._message_for(
            recipient_email=recipient_email,
            raw_token=raw_token,
            expires_at=expires_at,
        )
        await asyncio.to_thread(self._send_message, message)
        logger.info(
            "password.recovery.delivery.completed",
            extra={
                "user_id": str(user_id),
                "smtp_host": self._settings.host,
                "correlation_id": str(correlation_id),
            },
        )

    def _message_for(self, *, recipient_email: str, raw_token: str, expires_at) -> EmailMessage:
        reset_link = f"{self._settings.reset_url_base}?{urlencode({'token': raw_token})}"
        message = EmailMessage()
        message["From"] = self._settings.from_email
        message["To"] = recipient_email
        message["Subject"] = "Muxivo Console password recovery"
        message.set_content(
            "\n".join(
                (
                    "A password recovery request was made for your Muxivo Console account.",
                    "",
                    "Use this recovery link:",
                    reset_link,
                    "",
                    "If your Console UI asks for a token directly, use this token:",
                    raw_token,
                    "",
                    f"This recovery token expires at {expires_at.isoformat()}.",
                    "If you did not request this, you can ignore this email.",
                )
            )
        )
        return message

    def _send_message(self, message: EmailMessage) -> None:
        with self._smtp_factory(
            self._settings.host,
            self._settings.port,
            timeout=self._timeout_seconds,
        ) as smtp:
            if self._settings.starttls:
                smtp.starttls()
            if self._settings.username and self._settings.password:
                smtp.login(self._settings.username, self._settings.password)
            smtp.send_message(message)
