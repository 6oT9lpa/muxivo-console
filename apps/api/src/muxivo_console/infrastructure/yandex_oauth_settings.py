"""Yandex ID OAuth configuration value object."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class YandexOAuthSettings:
    """Validated Yandex ID OAuth client credentials and callback URI."""

    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
