"""Validated Telegram Login OIDC configuration."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelegramOAuthSettings:
    """Telegram Login client credentials and the registered callback URI."""

    client_id: str
    client_secret: str
    redirect_uri: str
