"""Shared SMTP transport with safe, structured delivery-stage logging."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from uuid import UUID

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings

logger = logging.getLogger(__name__)


class SmtpMailTransport:
    """Submit already-rendered messages through an authenticated SMTP relay."""

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
        message: EmailMessage,
        *,
        operation: str,
        resource_id: UUID,
        correlation_id: UUID,
    ) -> None:
        """Send a message without putting recipients, bodies or credentials in logs."""
        context = {
            "operation": operation,
            "resource_id": str(resource_id),
            "smtp_host": self._settings.host,
            "smtp_port": self._settings.port,
            "correlation_id": str(correlation_id),
        }
        logger.info("smtp.delivery.started", extra=context)
        try:
            await asyncio.to_thread(self._send_message, message, context)
        except Exception as error:
            logger.error(
                "smtp.delivery.failed",
                extra={**context, "error_type": type(error).__name__},
            )
            raise
        logger.info("smtp.delivery.completed", extra=context)

    def _send_message(self, message: EmailMessage, context: dict[str, str | int]) -> None:
        with self._smtp_factory(
            self._settings.host,
            self._settings.port,
            timeout=self._timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            logger.info("smtp.delivery.connected", extra=context)
            if self._settings.starttls:
                smtp.starttls()
                smtp.ehlo()
                logger.info("smtp.delivery.tls_negotiated", extra=context)
            if self._settings.username and self._settings.password:
                smtp.login(self._settings.username, self._settings.password)
                logger.info("smtp.delivery.authenticated", extra=context)
            smtp.send_message(message)
            logger.info("smtp.delivery.message_submitted", extra=context)
