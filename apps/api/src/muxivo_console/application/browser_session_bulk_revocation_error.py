"""Errors for bulk browser session revocation."""


class BrowserSessionBulkRevocationRejectedError(PermissionError):
    """Raised when bulk session revocation must fail closed."""
