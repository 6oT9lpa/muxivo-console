import logging
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import uuid4

import pytest
from muxivo_console.infrastructure.notifications import (
    SmtpOrganizationInvitationNotifier,
    SmtpPasswordRecoveryNotifier,
)
from muxivo_console.infrastructure.settings import SmtpPasswordRecoverySettings


class FakeSmtp:
    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ehlo_calls = 0
        self.started_tls = False
        self.login_arguments: tuple[str, str] | None = None
        self.message: EmailMessage | None = None

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_) -> bool:
        return False

    def ehlo(self) -> None:
        self.ehlo_calls += 1

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_arguments = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


@pytest.mark.asyncio
async def test_smtp_password_recovery_notifier_sends_reset_message_without_token_logs(
    caplog,
) -> None:
    fake_smtp: FakeSmtp | None = None

    def smtp_factory(host: str, port: int, *, timeout: float) -> FakeSmtp:
        nonlocal fake_smtp
        fake_smtp = FakeSmtp(host, port, timeout=timeout)
        return fake_smtp

    notifier = SmtpPasswordRecoveryNotifier(
        SmtpPasswordRecoverySettings(
            host="smtp.internal",
            port=587,
            from_email="security@muxivo.test",
            reset_url_base="https://console.muxivo.test/recover",
            username="smtp-user",
            password="smtp-password",
            starttls=True,
        ),
        smtp_factory=smtp_factory,
        timeout_seconds=3,
    )
    caplog.set_level(logging.INFO)

    await notifier.send(
        user_id=uuid4(),
        recipient_email="creator@example.com",
        raw_token="opaque-recovery-token",
        expires_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
        correlation_id=uuid4(),
    )

    assert fake_smtp is not None
    assert fake_smtp.host == "smtp.internal"
    assert fake_smtp.port == 587
    assert fake_smtp.timeout == 3
    assert fake_smtp.ehlo_calls == 2
    assert fake_smtp.started_tls is True
    assert fake_smtp.login_arguments == ("smtp-user", "smtp-password")
    assert fake_smtp.message is not None
    assert fake_smtp.message["From"] == "security@muxivo.test"
    assert fake_smtp.message["To"] == "creator@example.com"
    body = fake_smtp.message.get_content()
    assert "https://console.muxivo.test/recover?token=opaque-recovery-token" in body
    assert "opaque-recovery-token" in body
    assert "opaque-recovery-token" not in caplog.text
    assert "smtp.delivery.connected" in caplog.text
    assert "smtp.delivery.tls_negotiated" in caplog.text
    assert "smtp.delivery.authenticated" in caplog.text
    assert "smtp.delivery.message_submitted" in caplog.text


@pytest.mark.asyncio
async def test_smtp_organization_invitation_notifier_sends_link_without_token_logs(
    caplog,
) -> None:
    fake_smtp: FakeSmtp | None = None

    def smtp_factory(host: str, port: int, *, timeout: float) -> FakeSmtp:
        nonlocal fake_smtp
        fake_smtp = FakeSmtp(host, port, timeout=timeout)
        return fake_smtp

    notifier = SmtpOrganizationInvitationNotifier(
        SmtpPasswordRecoverySettings(
            host="connect.smtp.bz",
            port=587,
            from_email="security@muxivo.test",
            reset_url_base="https://console.muxivo.test/recover",
            invitation_url_base="https://console.muxivo.test/accept-invitation",
            username="smtp-user",
            password="smtp-password",
            starttls=True,
        ),
        smtp_factory=smtp_factory,
        timeout_seconds=3,
    )
    caplog.set_level(logging.INFO)

    delivered = await notifier.send(
        invitation_id=uuid4(),
        organization_name="Creator community",
        recipient_email="invitee@example.com",
        role="viewer",
        raw_token="opaque-invitation-token",
        expires_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
        correlation_id=uuid4(),
    )

    assert delivered is True
    assert fake_smtp is not None
    assert fake_smtp.host == "connect.smtp.bz"
    assert fake_smtp.port == 587
    assert fake_smtp.timeout == 3
    assert fake_smtp.ehlo_calls == 2
    assert fake_smtp.started_tls is True
    assert fake_smtp.login_arguments == ("smtp-user", "smtp-password")
    assert fake_smtp.message is not None
    assert fake_smtp.message["From"] == "security@muxivo.test"
    assert fake_smtp.message["To"] == "invitee@example.com"
    assert "https://console.muxivo.test/accept-invitation?token=opaque-invitation-token" in (
        fake_smtp.message.get_content()
    )
    assert "opaque-invitation-token" not in caplog.text


@pytest.mark.asyncio
async def test_smtp_transport_logs_safe_failure_without_message_contents(caplog) -> None:
    def failing_smtp_factory(host: str, port: int, *, timeout: float):
        raise RuntimeError("opaque-recovery-token must not be logged")

    notifier = SmtpPasswordRecoveryNotifier(
        SmtpPasswordRecoverySettings(
            host="smtp.internal",
            port=587,
            from_email="security@muxivo.test",
            reset_url_base="https://console.muxivo.test/recover",
            username="smtp-user",
            password="smtp-password",
            starttls=True,
        ),
        smtp_factory=failing_smtp_factory,
    )
    caplog.set_level(logging.INFO)

    with pytest.raises(RuntimeError, match="opaque-recovery-token"):
        await notifier.send(
            user_id=uuid4(),
            recipient_email="creator@example.com",
            raw_token="opaque-recovery-token",
            expires_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
            correlation_id=uuid4(),
        )

    assert "smtp.delivery.failed" in caplog.text
    assert "opaque-recovery-token must not be logged" not in caplog.text
    assert "smtp-password" not in caplog.text
