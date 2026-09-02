"""SMTP password recovery notification adapter."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlencode
from uuid import UUID

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings
from muxivo_console.infrastructure.smtp_mail_transport import SmtpMailTransport

logger = logging.getLogger(__name__)


class SmtpPasswordRecoveryNotifier:
    """Render and deliver first-party password recovery messages."""

    def __init__(
        self,
        settings: SmtpPasswordRecoverySettings,
        *,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
        timeout_seconds: float = 10.0,
        transport: SmtpMailTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport or SmtpMailTransport(
            settings,
            smtp_factory=smtp_factory,
            timeout_seconds=timeout_seconds,
        )

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        raw_token: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.info(
            "password.recovery.delivery.started",
            extra={"user_id": str(user_id), "correlation_id": str(correlation_id)},
        )
        message = self._message_for(
            recipient_email=recipient_email,
            raw_token=raw_token,
            expires_at=expires_at,
        )
        await self._transport.send(
            message,
            operation="password_recovery",
            resource_id=user_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "password.recovery.delivery.completed",
            extra={"user_id": str(user_id), "correlation_id": str(correlation_id)},
        )

    def _message_for(
        self,
        *,
        recipient_email: str,
        raw_token: str,
        expires_at: datetime,
    ) -> EmailMessage:
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
