"""Logging adapter that strips credentials before records reach handlers."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from muxivo_console.domain.redaction import redact_secret

_RESERVED_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class SecretRedactionFilter(logging.Filter):
    """Best-effort logging filter for structured extras and free-text messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secret(record.msg)
        if record.args:
            record.args = redact_secret(record.args)
        for key, value in list(record.__dict__.items()):
            if key not in _RESERVED_RECORD_KEYS:
                setattr(record, key, redact_secret({key: value})[key])
        return True


def install_secret_redaction_filter(loggers: Iterable[logging.Logger] | None = None) -> None:
    """Install a redaction filter once on known Console loggers and handlers."""
    redaction_filter = SecretRedactionFilter()
    targets = list(loggers) if loggers is not None else _default_console_loggers()
    for logger in targets:
        _add_filter_once(logger, redaction_filter)
        for handler in logger.handlers:
            _add_filter_once(handler, redaction_filter)
    for handler in logging.getLogger().handlers:
        _add_filter_once(handler, redaction_filter)


def _default_console_loggers() -> list[logging.Logger]:
    loggers = [logging.getLogger(), logging.getLogger("muxivo_console")]
    for name, registered_logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("muxivo_console") and isinstance(registered_logger, logging.Logger):
            loggers.append(registered_logger)
    return loggers


def _add_filter_once(target: logging.Logger | logging.Handler, filter_: logging.Filter) -> None:
    if any(isinstance(existing, SecretRedactionFilter) for existing in target.filters):
        return
    target.addFilter(filter_)
