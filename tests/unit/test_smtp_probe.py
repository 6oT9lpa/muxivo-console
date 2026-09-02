import logging

import pytest
from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings
from muxivo_console.infrastructure.smtp_probe import SmtpConnectivityProbe


class FakeSmtp:
    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ehlo_count = 0
        self.started_tls = False
        self.login_arguments: tuple[str, str] | None = None

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_) -> bool:
        return False

    def ehlo(self) -> None:
        self.ehlo_count += 1

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_arguments = (username, password)


def test_smtp_probe_authenticates_without_sending_a_message() -> None:
    fake_smtp: FakeSmtp | None = None

    def smtp_factory(host: str, port: int, *, timeout: float) -> FakeSmtp:
        nonlocal fake_smtp
        fake_smtp = FakeSmtp(host, port, timeout=timeout)
        return fake_smtp

    SmtpConnectivityProbe(
        SmtpPasswordRecoverySettings(
            host="connect.smtp.bz",
            port=587,
            from_email="security@muxivo.test",
            reset_url_base="https://console.muxivo.test/recover",
            username="smtp-user",
            password="smtp-password",
        ),
        smtp_factory=smtp_factory,
        timeout_seconds=3,
    ).probe()

    assert fake_smtp is not None
    assert fake_smtp.host == "connect.smtp.bz"
    assert fake_smtp.port == 587
    assert fake_smtp.timeout == 3
    assert fake_smtp.ehlo_count == 2
    assert fake_smtp.started_tls is True
    assert fake_smtp.login_arguments == ("smtp-user", "smtp-password")


def test_smtp_probe_rejects_missing_credentials_without_transport_login(caplog) -> None:
    caplog.set_level(logging.INFO, logger="muxivo_console.infrastructure.smtp_probe")

    with pytest.raises(ValueError, match="username and password"):
        SmtpConnectivityProbe(
            SmtpPasswordRecoverySettings(
                host="connect.smtp.bz",
                port=587,
                from_email="security@muxivo.test",
                reset_url_base="https://console.muxivo.test/recover",
            ),
            smtp_factory=lambda *_, **__: FakeSmtp("connect.smtp.bz", 587, timeout=3),
        ).probe()

    assert "smtp-password" not in caplog.text
