"""Errors for current browser session reauthentication."""


class BrowserSessionReauthenticationRejectedError(PermissionError):
    """Publicly safe failure for current-session reauthentication."""
