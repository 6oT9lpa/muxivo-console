"""Twitch Control API adapters that keep Twitch credentials outside Console."""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import LoginIdentityReader
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.connection_reconciliation import (
    ConnectionReconciliationDecision,
    ConnectionReconciliationReason,
)
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.infrastructure.discord_control_api import HmacControlAssertionIssuer


@dataclass(frozen=True, slots=True)
class TwitchPlatformHealthReader:
    """Read browser-safe Twitch connection health without exposing Twitch credentials."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_twitch_control_base_url(self.base_url, self.allow_insecure_http)

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
                "Twitch Control API health request failed."
            ) from error
        return _parse_twitch_health(payload)


@dataclass(frozen=True, slots=True)
class TwitchPlatformConnectionVerifier:
    """Ask Twitch to re-check native authority before Console links a channel."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    identities: LoginIdentityReader
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_twitch_control_base_url(self.base_url, self.allow_insecure_http)

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        if platform is not Platform.TWITCH:
            return False
        platform_subject = await self.identities.find_provider_subject(
            user_id=actor_id, provider=LoginIdentityProvider.TWITCH
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
                "Twitch Control API connection verification failed."
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("verified"), bool):
            raise PlatformControlUnavailableError(
                "Twitch Control API returned an invalid connection verification payload."
            )
        return payload["verified"]


@dataclass(frozen=True, slots=True)
class TwitchPlatformConnectionReconciliationProbe:
    """Ask Twitch Control API for a secret-free lifecycle reconciliation decision."""

    base_url: str
    assertions: HmacControlAssertionIssuer
    system_actor_id: UUID
    timeout: float = 5.0
    transport: httpx.AsyncBaseTransport | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        _validate_twitch_control_base_url(self.base_url, self.allow_insecure_http)

    async def inspect_connection(
        self, *, connection: PlatformConnection, correlation_id: UUID
    ) -> ConnectionReconciliationDecision:
        if connection.platform is not Platform.TWITCH:
            return ConnectionReconciliationDecision(
                target_status=connection.status,
                reason=ConnectionReconciliationReason.HEALTHY,
            )
        assertion = self.assertions.issue(
            actor_id=self.system_actor_id,
            organization_id=connection.organization_id,
            resource=AuthorizationResource.PLATFORM_CONNECTIONS,
            action=AuthorizationAction.READ,
            correlation_id=correlation_id,
            platform_resource_id=connection.external_resource_id,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    "/control/v1/organizations/"
                    f"{connection.organization_id}/connections/"
                    f"{connection.external_resource_id}/reconciliation",
                    headers={"Authorization": f"Bearer {assertion}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise PlatformControlUnavailableError(
                "Twitch Control API connection reconciliation request failed."
            ) from error
        return _parse_twitch_connection_reconciliation_decision(payload)


def _parse_twitch_connection_reconciliation_decision(
    payload: Any,
) -> ConnectionReconciliationDecision:
    if not isinstance(payload, dict):
        raise PlatformControlUnavailableError(
            "Twitch Control API returned an invalid connection reconciliation payload."
        )
    try:
        target_status = payload["target_status"]
        reason = payload["reason"]
        if not isinstance(target_status, str) or not isinstance(reason, str):
            raise ValueError("Connection reconciliation fields must be strings.")
        return ConnectionReconciliationDecision(
            target_status=ConnectionStatus(target_status),
            reason=ConnectionReconciliationReason(reason),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Twitch Control API returned an invalid connection reconciliation decision."
        ) from error


def _parse_twitch_health(payload: Any) -> PlatformHealth:
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        raise PlatformControlUnavailableError(
            "Twitch Control API returned an invalid health payload."
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
                    key=_twitch_health_signal_key(name),
                    display_name=name,
                    value=value,
                    status=HealthStatus(status),
                    latency_ms=latency_ms,
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise PlatformControlUnavailableError(
            "Twitch Control API returned an invalid health signal."
        ) from error
    return PlatformHealth(platform=Platform.TWITCH, signals=tuple(signals))


def _twitch_health_signal_key(name: str) -> str:
    return "twitch." + "".join(
        character.lower() if character.isalnum() else "-" for character in name
    ).strip("-")


def _validate_twitch_control_base_url(base_url: str, allow_insecure_http: bool) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Twitch Control API base URL must be an absolute service URL.")
    if parsed.scheme == "http" and not allow_insecure_http:
        raise ValueError("Twitch Control API base URL must use HTTPS outside development.")
