"""Errors for browser session listing."""


class BrowserSessionListRejectedError(PermissionError):
    """Raised when session listing must fail closed."""
