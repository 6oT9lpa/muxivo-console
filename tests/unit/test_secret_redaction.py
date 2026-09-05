import logging

from muxivo_console.domain.redaction import REDACTED_SECRET, redact_secret, redact_secret_text
from muxivo_console.infrastructure.discord_oauth_settings import DiscordOAuthSettings
from muxivo_console.infrastructure.logging_redaction import SecretRedactionFilter
from muxivo_console.infrastructure.smtp_password_recovery_settings import (
    SmtpPasswordRecoverySettings,
)
from muxivo_console.infrastructure.twitch_control_settings import TwitchControlSettings


def test_secret_redaction_recurses_through_structured_payloads() -> None:
    payload = {
        "access_token": "discord-access-token",
        "connection": {
            "external_resource_id": "guild-123",
            "refresh_token": "discord-refresh-token",
        },
        "events": [{"client_secret": "oauth-client-secret"}],
    }

    redacted = redact_secret(payload)

    assert redacted["access_token"] == REDACTED_SECRET
    assert redacted["connection"]["external_resource_id"] == "guild-123"
    assert redacted["connection"]["refresh_token"] == REDACTED_SECRET
    assert redacted["events"][0]["client_secret"] == REDACTED_SECRET


def test_secret_redaction_scrubs_common_free_text_shapes() -> None:
    message = (
        "Authorization: Bearer platform-secret access_token=discord-access "
        'client_secret="oauth-client-secret" password=plain-text'
    )

    redacted = redact_secret_text(message)

    assert "platform-secret" not in redacted
    assert "discord-access" not in redacted
    assert "oauth-client-secret" not in redacted
    assert "plain-text" not in redacted
    assert REDACTED_SECRET in redacted


def test_secret_redaction_filter_sanitizes_messages_and_structured_extras() -> None:
    record = logging.LogRecord(
        name="muxivo_console.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="callback failed with refresh_token=discord-refresh-token",
        args=(),
        exc_info=None,
    )
    record.access_token = "discord-access-token"

    SecretRedactionFilter().filter(record)

    assert "discord-refresh-token" not in record.getMessage()
    assert record.access_token == REDACTED_SECRET


def test_secret_bearing_configuration_repr_never_contains_credentials() -> None:
    values = (
        repr(DiscordOAuthSettings("client-id", "oauth-secret", "https://example.test/callback")),
        repr(
            SmtpPasswordRecoverySettings(
                host="smtp.example.test",
                port=587,
                from_email="security@example.test",
                reset_url_base="https://example.test/recover",
                username="smtp-user",
                password="smtp-password",
            )
        ),
        repr(TwitchControlSettings("https://twitch-control.test", b"signing-key")),
    )

    rendered = " ".join(values)
    assert "oauth-secret" not in rendered
    assert "smtp-password" not in rendered
    assert "signing-key" not in rendered
