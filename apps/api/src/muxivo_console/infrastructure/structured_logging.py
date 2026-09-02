"""Structured JSON logging for production process handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from muxivo_console.domain.redaction import redact_secret, redact_secret_text

_BASE_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
_FORMATTER_ONLY_KEYS = frozenset(
    {
        "asctime",
        "event",
        "exception",
        "level",
        "logger",
        "message",
        "process_id",
        "stack",
        "timestamp",
    }
)


class StructuredJsonFormatter(logging.Formatter):
    """Serialize log events as one redacted JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Build a stable event envelope without exposing raw access metadata."""
        message = self._safe_message(record)
        record.message = message
        payload: dict[str, object] = {
            "timestamp": _format_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "event": message,
            "message": message,
            "process_id": record.process,
        }
        payload.update(self._structured_extras(record))

        if record.name == "uvicorn.access":
            payload["event"] = "http.access"
            payload["message"] = "http.access"
            record.message = "http.access"
            payload.update(_access_fields(record))

        if record.exc_info is not None:
            payload["exception"] = _exception_payload(self, record)
        if record.stack_info:
            payload["stack"] = redact_secret_text(record.stack_info)
        return json.dumps(
            redact_secret(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )

    @staticmethod
    def _safe_message(record: logging.LogRecord) -> str:
        """Render a message before final redaction, even for unusual log values."""
        try:
            return redact_secret_text(record.getMessage())
        except Exception as error:  # pragma: no cover - defensive logging fallback
            return f"[unrenderable log message: {type(error).__name__}]"

    @staticmethod
    def _structured_extras(record: logging.LogRecord) -> dict[str, object]:
        """Copy only caller-provided fields, leaving the standard envelope stable."""
        reserved = _BASE_RECORD_KEYS | _FORMATTER_ONLY_KEYS
        return {
            key: redact_secret(value)
            for key, value in record.__dict__.items()
            if key not in reserved
        }


def install_structured_logging(
    handlers: Iterable[logging.Handler] | None = None,
) -> None:
    """Use the JSON formatter on all handlers currently configured by the process."""
    configured_handlers = tuple(handlers) if handlers is not None else _configured_handlers()
    formatter = StructuredJsonFormatter()
    configured_handler_ids: set[int] = set()
    for handler in configured_handlers:
        handler_id = id(handler)
        if handler_id in configured_handler_ids:
            continue
        configured_handler_ids.add(handler_id)
        handler.setFormatter(formatter)


def _configured_handlers() -> list[logging.Handler]:
    """Collect root and named-logger handlers, including Uvicorn's access handler."""
    handlers: list[logging.Handler] = list(logging.getLogger().handlers)
    for registered_logger in logging.Logger.manager.loggerDict.values():
        if isinstance(registered_logger, logging.Logger):
            handlers.extend(registered_logger.handlers)
    return handlers


def _format_timestamp(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _access_fields(record: logging.LogRecord) -> dict[str, object]:
    """Map Uvicorn access arguments while deliberately omitting the client address."""
    args = record.args
    if not isinstance(args, tuple) or len(args) < 5:
        return {}
    _, method, full_path, http_version, status_code = args[:5]
    parsed_path = urlsplit(str(full_path)).path or "/"
    return {
        "method": redact_secret_text(str(method)),
        "path": redact_secret_text(parsed_path),
        "http_version": redact_secret_text(str(http_version)),
        "status_code": status_code,
    }


def _exception_payload(
    formatter: logging.Formatter,
    record: logging.LogRecord,
) -> dict[str, str]:
    exception_type, exception_value, _ = record.exc_info  # type: ignore[misc]
    traceback = formatter.formatException(record.exc_info)
    return {
        "type": getattr(exception_type, "__name__", str(exception_type)),
        "message": redact_secret_text(str(exception_value)),
        "traceback": redact_secret_text(traceback),
    }


def _json_default(value: object) -> object:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)
