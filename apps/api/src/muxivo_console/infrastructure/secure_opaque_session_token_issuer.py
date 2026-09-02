"""Opaque browser session token issuer."""

import secrets


class SecureOpaqueSessionTokenIssuer:
    """Create a 256-bit opaque token suitable for an HttpOnly browser cookie."""

    def issue(self) -> str:
        return secrets.token_urlsafe(32)
