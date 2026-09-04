"""Styled SMTP notification for e-mail/password registration verification."""

from __future__ import annotations

import html
import logging
import smtplib
from collections.abc import Callable
from datetime import datetime
from email.message import EmailMessage
from uuid import UUID

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings
from muxivo_console.infrastructure.smtp_mail_transport import SmtpMailTransport

logger = logging.getLogger(__name__)


class SmtpEmailPasswordRegistrationVerificationNotifier:
    """Render a branded code message without logging the recipient or code."""

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
        registration_id: UUID,
        recipient_email: str,
        verification_code: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.info(
            "auth.email_password.verification_delivery.started",
            extra={"registration_id": str(registration_id), "correlation_id": str(correlation_id)},
        )
        message = self._message_for(
            recipient_email=recipient_email,
            verification_code=verification_code,
            expires_at=expires_at,
        )
        await self._transport.send(
            message,
            operation="email_password_registration_verification",
            resource_id=registration_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "auth.email_password.verification_delivery.completed",
            extra={"registration_id": str(registration_id), "correlation_id": str(correlation_id)},
        )

    def _message_for(
        self,
        *,
        recipient_email: str,
        verification_code: str,
        expires_at: datetime,
    ) -> EmailMessage:
        safe_code = html.escape(verification_code)
        safe_expiry = html.escape(expires_at.isoformat())
        text = "\n".join(
            (
                "Confirm your Muxivo Console e-mail address.",
                "",
                f"Your confirmation code is: {verification_code}",
                "",
                f"This code expires at {expires_at.isoformat()}.",
                "If you did not start this registration, ignore this message.",
            )
        )
        content = "\n".join(
            (
                "<!doctype html>",
                '<html lang="en">',
                '  <body style="margin:0;background:#050505;color:#f4f4f5;'
                'font-family:Arial,sans-serif;">',
                '    <div style="max-width:560px;margin:32px auto;padding:32px;'
                'background:#0b0b0c;border:1px solid #27272a;border-radius:14px;">',
                '      <p style="margin:0;color:#a5b4fc;font-size:12px;font-weight:700;'
                'letter-spacing:2px;">MUXIVO CONSOLE</p>',
                '      <h1 style="margin:18px 0 10px;font-size:28px;line-height:1.1;">'
                "Confirm your e-mail</h1>",
                '      <p style="margin:0;color:#a1a1aa;line-height:1.6;">'
                "Enter this code in the registration window to activate your Console account.</p>",
                '      <div style="margin:26px 0;padding:20px;text-align:center;'
                'background:#050505;border:1px solid #3f3f46;border-radius:10px;">',
                f'        <span style="color:#c7d2fe;font-size:34px;font-weight:800;'
                f'letter-spacing:9px;">{safe_code}</span>',
                "      </div>",
                '      <p style="margin:0;color:#a1a1aa;font-size:13px;line-height:1.6;">'
                f"The code expires at {safe_expiry}.</p>",
                '      <p style="margin:18px 0 0;padding-top:18px;color:#fbbf24;'
                'border-top:1px solid #27272a;font-size:13px;line-height:1.6;">'
                "If you did not request this registration, ignore this message. "
                "Your account will not be created without the code.</p>",
                "    </div>",
                "  </body>",
                "</html>",
            )
        )
        message = EmailMessage()
        message["From"] = self._settings.from_email
        message["To"] = recipient_email
        message["Subject"] = "Confirm your Muxivo Console e-mail"
        message.set_content(text)
        message.add_alternative(content, subtype="html")
        return message
