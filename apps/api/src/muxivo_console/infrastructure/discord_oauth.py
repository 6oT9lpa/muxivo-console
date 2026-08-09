"""Discord OAuth authorization-code adapter for verified Console identity linking."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx


class DiscordOAuthUnavailableError(RuntimeError):
    """Raised when Discord OAuth cannot safely resolve a provider subject."""


@dataclass(frozen=True, slots=True)
class DiscordOAuthClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    api_base_url: str = "https://discord.com/api/v10"
    authorize_url: str = "https://discord.com/oauth2/authorize"
    timeout: float = 10.0
    transport: httpx.AsyncBaseTransport | None = None

    def __post_init__(self) -> None:
        if (
            not self.client_id
            or not self.client_secret
            or not self.redirect_uri.startswith("https://")
        ):
            raise ValueError("Discord OAuth credentials and HTTPS redirect URI are required.")

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "identify guilds",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.authorize_url}?{query}"

    async def resolve_subject(self, *, authorization_code: str, code_verifier: str) -> str:
        try:
            async with httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                token_response = await client.post(
                    "/oauth2/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self.redirect_uri,
                        "code_verifier": code_verifier,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                token_response.raise_for_status()
                token_payload = token_response.json()
                access_token = (
                    token_payload.get("access_token") if isinstance(token_payload, dict) else None
                )
                if not isinstance(access_token, str) or not access_token:
                    raise ValueError("Discord token response did not contain an access token.")
                user_response = await client.get(
                    "/users/@me", headers={"Authorization": f"Bearer {access_token}"}
                )
                user_response.raise_for_status()
                user_payload = user_response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DiscordOAuthUnavailableError("Discord OAuth verification failed.") from error
        subject = user_payload.get("id") if isinstance(user_payload, dict) else None
        if not isinstance(subject, str) or not subject.isdigit() or len(subject) > 255:
            raise DiscordOAuthUnavailableError("Discord OAuth returned an invalid user subject.")
        return subject
