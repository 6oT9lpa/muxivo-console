"""Run a non-delivery SMTP.BZ connectivity probe from environment variables."""

from __future__ import annotations

import logging
import os
import sys

from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings
from muxivo_console.infrastructure.smtp_probe import SmtpConnectivityProbe

logger = logging.getLogger("muxivo_console.smtp_probe")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be configured.")
    return value


def _port(name: str) -> int:
    try:
        value = int(_required(name))
    except ValueError as error:
        raise ValueError(f"{name} must be a TCP port.") from error
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535.")
    return value


def _boolean(name: str, *, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean.")


def _settings_from_environment() -> SmtpPasswordRecoverySettings:
    return SmtpPasswordRecoverySettings(
        host=_required("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_HOST"),
        port=_port("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PORT"),
        from_email=_required("MUXIVO_CONSOLE_PASSWORD_RECOVERY_FROM_EMAIL"),
        reset_url_base=_required("MUXIVO_CONSOLE_PASSWORD_RECOVERY_RESET_URL_BASE"),
        username=_required("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_USERNAME"),
        password=_required("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD"),
        starttls=_boolean("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_STARTTLS", default=True),
    )


def main() -> int:
    """Return a process status while keeping all secret values out of output."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        SmtpConnectivityProbe(_settings_from_environment()).probe()
    except Exception as error:
        logger.error(
            "smtp.probe.configuration_or_transport_failed",
            extra={"error_type": type(error).__name__},
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
