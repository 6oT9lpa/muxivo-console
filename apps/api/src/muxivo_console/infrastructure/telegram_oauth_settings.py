"""Validated Telegram Login OIDC configuration."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TelegramOAuthSettings:
    """Telegram Login client credentials and the registered callback URI."""

    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
