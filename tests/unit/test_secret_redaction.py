import logging

from muxivo_console.domain.redaction import REDACTED_SECRET, redact_secret, redact_secret_text
from muxivo_console.infrastructure.logging_redaction import SecretRedactionFilter


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
