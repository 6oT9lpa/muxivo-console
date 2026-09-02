"""Non-delivery SMTP connectivity and authentication probe."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings

logger = logging.getLogger(__name__)


class SmtpConnectivityProbe:
    """Verify an SMTP relay without sending a message or logging credentials."""

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

    def probe(self) -> None:
        """Open a session, negotiate TLS and authenticate without delivering mail."""
        logger.info(
            "smtp.probe.started",
            extra={
                "smtp_host": self._settings.host,
                "smtp_port": self._settings.port,
                "starttls": self._settings.starttls,
            },
        )
        try:
            with self._smtp_factory(
                self._settings.host,
                self._settings.port,
                timeout=self._timeout_seconds,
            ) as smtp:
                smtp.ehlo()
                logger.info("smtp.probe.connected", extra={"smtp_host": self._settings.host})
                if self._settings.starttls:
                    smtp.starttls()
                    smtp.ehlo()
                    logger.info(
                        "smtp.probe.tls_negotiated",
                        extra={"smtp_host": self._settings.host},
                    )
                if not self._settings.username or not self._settings.password:
                    raise ValueError("SMTP username and password are required for the probe.")
                smtp.login(self._settings.username, self._settings.password)
                logger.info(
                    "smtp.probe.authenticated",
                    extra={"smtp_host": self._settings.host},
                )
        except Exception as error:
            logger.error(
                "smtp.probe.failed",
                extra={
                    "smtp_host": self._settings.host,
                    "smtp_port": self._settings.port,
                    "error_type": type(error).__name__,
                },
            )
            raise
        logger.info("smtp.probe.completed", extra={"smtp_host": self._settings.host})
