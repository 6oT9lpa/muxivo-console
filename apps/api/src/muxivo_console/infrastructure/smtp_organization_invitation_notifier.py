"""SMTP organization invitation notification adapter."""

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


class SmtpOrganizationInvitationNotifier:
    """Render and deliver organization invitation links."""

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
        invitation_id: UUID,
        organization_name: str,
        recipient_email: str,
        role: str,
        raw_token: str,
        expires_at: datetime,
        correlation_id: UUID,
    ) -> bool:
        logger.info(
            "organization.invitation.delivery.started",
            extra={
                "invitation_id": str(invitation_id),
                "role": role,
                "correlation_id": str(correlation_id),
            },
        )
        message = self._message_for(
            organization_name=organization_name,
            recipient_email=recipient_email,
            role=role,
            raw_token=raw_token,
            expires_at=expires_at,
        )
        await self._transport.send(
            message,
            operation="organization_invitation",
            resource_id=invitation_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "organization.invitation.delivery.completed",
            extra={
                "invitation_id": str(invitation_id),
                "correlation_id": str(correlation_id),
            },
        )
        return True

    def _message_for(
        self,
        *,
        organization_name: str,
        recipient_email: str,
        role: str,
        raw_token: str,
        expires_at: datetime,
    ) -> EmailMessage:
        invitation_url_base = self._settings.invitation_url_base or _derived_invitation_url_base(
            self._settings.reset_url_base
        )
        invitation_link = f"{invitation_url_base}?{urlencode({'token': raw_token})}"
        message = EmailMessage()
        message["From"] = self._settings.from_email
        message["To"] = recipient_email
        message["Subject"] = f"You have been invited to {organization_name} on Muxivo Console"
        message.set_content(
            "\n".join(
                (
                    f"You have been invited to join {organization_name} on Muxivo Console.",
                    f"Your organization role: {role}.",
                    "",
                    "Accept the invitation:",
                    invitation_link,
                    "",
                    f"This invitation expires at {expires_at.isoformat()}.",
                    "If you did not expect this invitation, you can ignore this email.",
                )
            )
        )
        return message


def _derived_invitation_url_base(reset_url_base: str) -> str:
    prefix, separator, _ = reset_url_base.rpartition("/")
    return f"{prefix if separator else reset_url_base}/accept-invitation"
