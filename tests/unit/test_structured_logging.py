import json
import logging
import sys
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

from muxivo_console.domain.redaction import REDACTED_SECRET
from muxivo_console.infrastructure.structured_logging import (
    StructuredJsonFormatter,
    install_structured_logging,
)


def test_formatter_emits_json_event_metadata_and_redacts_secrets() -> None:
    record = logging.LogRecord(
        name="muxivo_console.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="organization.member.updated",
        args=(),
        exc_info=None,
    )
    record.created = datetime(2026, 9, 2, 10, 11, 12, 345000, tzinfo=UTC).timestamp()
    record.correlation_id = uuid4()
    record.secret_token = "must-not-appear"
    record.nested = {"external_resource_id": "guild-123", "password": "also-hidden"}

    payload = json.loads(StructuredJsonFormatter().format(record))

    assert payload["timestamp"] == "2026-09-02T10:11:12.345Z"
    assert payload["event"] == "organization.member.updated"
    assert payload["message"] == "organization.member.updated"
    assert payload["correlation_id"] == str(record.correlation_id)
    assert payload["secret_token"] == REDACTED_SECRET
    assert payload["nested"] == {
        "external_resource_id": "guild-123",
        "password": REDACTED_SECRET,
    }


def test_formatter_normalizes_uvicorn_access_without_raw_client_address() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("203.0.113.10:43122", "GET", "/api/v1/session?token=secret", "1.1", 200),
        exc_info=None,
    )

    serialized = StructuredJsonFormatter().format(record)
    payload = json.loads(serialized)

    assert payload["event"] == "http.access"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/session"
    assert payload["http_version"] == "1.1"
    assert payload["status_code"] == 200
    assert "203.0.113.10" not in serialized
    assert "secret" not in serialized


def test_formatter_redacts_exception_message_and_traceback() -> None:
    try:
        raise RuntimeError("password=exception-password")
    except RuntimeError:
        record = logging.LogRecord(
            name="muxivo_console.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="operation.failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(StructuredJsonFormatter().format(record))

    assert payload["exception"]["type"] == "RuntimeError"
    assert REDACTED_SECRET in payload["exception"]["message"]
    assert "exception-password" not in json.dumps(payload)


def test_install_structured_logging_configures_supplied_handlers() -> None:
    handler = logging.StreamHandler(StringIO())

    install_structured_logging([handler, handler])

    assert isinstance(handler.formatter, StructuredJsonFormatter)
