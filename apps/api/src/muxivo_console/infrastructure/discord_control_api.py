"""Discord Control API adapter, isolated from Discord runtime persistence."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import Clock, LoginIdentityReader
from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class HmacControlAssertionIssuer:
    """Issues short-lived, audience-bound service assertions for one Control API."""

    issuer: str
    audience: str
    signing_key: bytes
    clock: Clock
    lifetime: timedelta = timedelta(seconds=60)

    def __post_init__(self) -> None:
        if len(self.signing_key) < 32:
            raise ValueError("Control assertion signing key must be at least 32 bytes.")
        if not self.issuer or not self.audience:
            raise ValueError("Control assertion issuer and audience must be non-empty.")

    def issue(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        resource: AuthorizationResource,
        action: AuthorizationAction,
        correlation_id: UUID,
        platform_subject: str | None = None,
    ) -> str:
        now = self.clock.now().astimezone(UTC)
        header = {"alg": "HS256", "typ": "JWT"}
        claims = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": str(actor_id),
            "organization_id": str(organization_id),
            "resource": resource.value,
            "action": action.value,
            "correlation_id": str(correlation_id),
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + self.lifetime).timestamp()),
        }
        if platform_subject is not None:
            claims["platform_subject"] = platform_subject
        encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
        encoded_claims = _base64url(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
        signature = hmac.new(self.signing_key, signing_input, hashlib.sha256).digest()
        return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


@dataclass(frozen=True, slots=True)
class DiscordControlApiCatalog:
    """Maps Discord's versioned control response to Console's neutral module model."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_control_base_url(self.base_url, self.allow_insecure_http)

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> tuple[ControlModule, ...]:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/modules",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError("Discord Control API request failed.") from error
        return _parse_discord_modules(payload)

    async def get_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth:
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    f"/control/v1/organizations/{organization_id}/health",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API health request failed."
            ) from error
        return _parse_discord_health(payload)


@dataclass(frozen=True, slots=True)
class DiscordPlatformConnectionVerifier:
    """Ask Discord to re-check native authority before Console links a guild."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    identities: LoginIdentityReader
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_control_base_url(self.base_url, self.allow_insecure_http)

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        if platform is not Platform.DISCORD:
            return False
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.DISCORD
        )
        if platform_subject is None:
            return False
        assertion = self.assertions.issue(
            actor_id=actor_id,
            organization_id=organization_id,
            resource=AuthorizationResource.PLATFORM_CONNECTIONS,
            action=AuthorizationAction.MANAGE,
            correlation_id=correlation_id,
            platform_subject=platform_subject,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"/control/v1/organizations/{organization_id}/connections/verify",
                    headers={"Authorization": f"Bearer {assertion}"},
                    json={"platform": platform.value, "external_resource_id": external_resource_id},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Discord Control API connection verification failed."
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("verified"), bool):
            raise PlatformControlUnavailableError(
                "Discord Control API returned an invalid connection verification payload."
            )
        return payload["verified"]


def _parse_discord_modules(payload: Any) -> tuple[ControlModule, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid module payload."
        )
    modules: list[ControlModule] = []
    try:
        for item in payload["items"]:
            if not isinstance(item, dict):
                raise ValueError("Module item must be an object.")
            if not all(
                isinstance(item.get(field), str)
                for field in ("key", "display_name", "platform", "capability", "status")
            ):
                raise ValueError("Module fields must be strings.")
            module = ControlModule(
                key=item["key"],
                display_name=item["display_name"],
                platform=Platform(item["platform"]),
                capability=ModuleCapability(item["capability"]),
                status=ModuleStatus(item["status"]),
            )
            if module.platform is not Platform.DISCORD:
                raise ValueError("Discord adapter cannot return another platform's module.")
            modules.append(module)
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid module."
        ) from error
    return tuple(modules)


def _parse_discord_health(payload: Any) -> PlatformHealth:
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid health payload."
        )
    signals: list[HealthSignal] = []
    try:
        for item in payload["signals"]:
            if not isinstance(item, dict):
                raise ValueError("Health signal must be an object.")
            name, value, status = item["name"], item["value"], item["status"]
            latency_ms = item.get("latency_ms")
            if (
                not isinstance(name, str)
                or not isinstance(value, str)
                or not isinstance(status, str)
            ):
                raise ValueError("Health signal fields must be strings.")
            if latency_ms is not None and (
                not isinstance(latency_ms, int) or isinstance(latency_ms, bool)
            ):
                raise ValueError("Health signal latency must be an integer.")
            signals.append(
                HealthSignal(
                    key=_health_signal_key(name),
                    display_name=name,
                    value=value,
                    status=HealthStatus(status),
                    latency_ms=latency_ms,
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Discord Control API returned an invalid health signal."
        ) from error
    return PlatformHealth(platform=Platform.DISCORD, signals=tuple(signals))


def _health_signal_key(name: str) -> str:
    return "discord." + "".join(
        character.lower() if character.isalnum() else "-" for character in name
    ).strip("-")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _validate_control_base_url(base_url: str, allow_insecure_http: bool) -> None:
    parsed = urlparse(base_url)
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes or not parsed.netloc or parsed.username:
        raise ValueError("Discord Control API base URL must be an absolute service URL.")
