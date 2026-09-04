"""SMTP notification sent after a password recovery completes."""

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


class SmtpPasswordRecoveryCompletionNotifier:
    """Deliver a token-free password-change confirmation through SMTP."""

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
        changed_at: datetime,
        correlation_id: UUID,
    ) -> None:
        logger.info(
            "password.recovery.completion_notification.started",
            extra={"user_id": str(user_id), "correlation_id": str(correlation_id)},
        )
        message = self._message_for(recipient_email=recipient_email, changed_at=changed_at)
        await self._transport.send(
            message,
            operation="password_recovery_completion",
            resource_id=user_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "password.recovery.completion_notification.completed",
            extra={"user_id": str(user_id), "correlation_id": str(correlation_id)},
        )

    def _message_for(self, *, recipient_email: str, changed_at: datetime) -> EmailMessage:
        safe_changed_at = html.escape(changed_at.isoformat())
        message = EmailMessage()
        message["From"] = self._settings.from_email
        message["To"] = recipient_email
        message["Subject"] = "Muxivo Console password changed"
        message.set_content(
            "\n".join(
                (
                    "Your Muxivo Console password was changed.",
                    "",
                    f"Changed at: {changed_at.isoformat()}.",
                    "If you did not make this change, secure your account immediately.",
                )
            )
        )
        message.add_alternative(
            "\n".join(
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
                    "Password changed</h1>",
                    '      <p style="margin:0;color:#a1a1aa;line-height:1.6;">'
                    "Your Muxivo Console password was changed successfully.</p>",
                    '      <p style="margin:24px 0 0;color:#a1a1aa;font-size:13px;'
                    f'line-height:1.6;">Changed at: {safe_changed_at}.</p>',
                    '      <p style="margin:18px 0 0;padding-top:18px;color:#fbbf24;'
                    'border-top:1px solid #27272a;font-size:13px;line-height:1.6;">'
                    "If you did not make this change, secure your account immediately and "
                    "contact support.</p>",
                    "    </div>",
                    "  </body>",
                    "</html>",
                )
            ),
            subtype="html",
        )
        return message
