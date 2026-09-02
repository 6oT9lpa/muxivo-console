"""Validate the public Console network surface without changing remote state."""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

logger = logging.getLogger("muxivo_console.production_network_preflight")

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
PUBLIC_HTTPS_PORT = 443

REQUIRED_SECURITY_HEADERS: tuple[str, ...] = (
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
)

DnsResolver = Callable[..., list[tuple[Any, ...]]]
TlsValidator = Callable[["NetworkPreflightSettings"], None]
HttpGetter = Callable[["NetworkPreflightSettings", str], tuple[int, Mapping[str, str]]]


@dataclass(frozen=True, slots=True)
class NetworkPreflightSettings:
    """Non-secret inputs required to validate the public Console surface."""

    public_base_url: str
    hostname: str
    expected_dns_ips: frozenset[str]
    timeout_seconds: float


def settings_from_environment(
    environment: Mapping[str, str] | None = None,
) -> NetworkPreflightSettings:
    """Build strict production preflight settings from environment variables."""
    values = os.environ if environment is None else environment
    public_base_url = _required(values, "MUXIVO_CONSOLE_PUBLIC_BASE_URL").rstrip("/")
    parsed_url = urlsplit(public_base_url)

    if parsed_url.scheme != "https":
        raise ValueError("MUXIVO_CONSOLE_PUBLIC_BASE_URL must use https.")
    if not parsed_url.hostname or parsed_url.path not in {"", "/"}:
        raise ValueError("MUXIVO_CONSOLE_PUBLIC_BASE_URL must contain only an HTTPS origin.")
    if parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
        raise ValueError("MUXIVO_CONSOLE_PUBLIC_BASE_URL must not contain credentials or extras.")
    try:
        explicit_port = parsed_url.port
    except ValueError as error:
        raise ValueError("MUXIVO_CONSOLE_PUBLIC_BASE_URL contains an invalid port.") from error
    if explicit_port not in {None, PUBLIC_HTTPS_PORT}:
        raise ValueError("MUXIVO_CONSOLE_PUBLIC_BASE_URL must use the standard HTTPS port.")

    expected_dns_ips = _parse_expected_dns_ips(_required(values, "MUXIVO_CONSOLE_EXPECTED_DNS_IPS"))
    timeout_seconds = _parse_timeout(
        values.get("MUXIVO_CONSOLE_NETWORK_PREFLIGHT_TIMEOUT_SECONDS", "")
    )

    return NetworkPreflightSettings(
        public_base_url=public_base_url,
        hostname=parsed_url.hostname,
        expected_dns_ips=expected_dns_ips,
        timeout_seconds=timeout_seconds,
    )


def validate_dns(
    settings: NetworkPreflightSettings,
    *,
    resolver: DnsResolver = socket.getaddrinfo,
) -> frozenset[str]:
    """Resolve the public hostname and require the approved ingress address."""
    logger.info(
        "production_preflight.stage_started stage=dns hostname=%s",
        settings.hostname,
        extra={"stage": "dns", "hostname": settings.hostname},
    )
    records = resolver(
        settings.hostname,
        PUBLIC_HTTPS_PORT,
        type=socket.SOCK_STREAM,
    )
    resolved_ips = frozenset(str(record[4][0]) for record in records if record[4])
    if not resolved_ips:
        raise OSError("public hostname has no address records")

    missing_ips = settings.expected_dns_ips - resolved_ips
    if missing_ips:
        raise OSError("approved ingress address is not present in DNS")

    logger.info(
        "production_preflight.stage_succeeded stage=dns resolved_ip_count=%s",
        len(resolved_ips),
        extra={"stage": "dns", "resolved_ip_count": len(resolved_ips)},
    )
    return resolved_ips


def validate_tls(
    settings: NetworkPreflightSettings,
    *,
    connector: Callable[..., Any] = socket.create_connection,
    context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
) -> None:
    """Perform normal certificate-chain and hostname validation for the origin."""
    logger.info(
        "production_preflight.stage_started stage=tls hostname=%s",
        settings.hostname,
        extra={"stage": "tls", "hostname": settings.hostname},
    )
    context = context_factory()
    with connector(
        (settings.hostname, PUBLIC_HTTPS_PORT),
        timeout=settings.timeout_seconds,
    ) as raw_socket:
        with context.wrap_socket(raw_socket, server_hostname=settings.hostname) as tls_socket:
            if not tls_socket.version():
                raise ssl.SSLError("TLS negotiation did not return a protocol version")
            protocol = tls_socket.version()

    logger.info(
        "production_preflight.stage_succeeded stage=tls protocol=%s",
        protocol,
        extra={"stage": "tls", "protocol": protocol},
    )


def fetch_http(
    settings: NetworkPreflightSettings,
    path: str,
    *,
    opener: Callable[..., Any] = urlopen,
) -> tuple[int, Mapping[str, str]]:
    """Fetch one public endpoint while returning status and headers only."""
    if not path.startswith("/"):
        raise ValueError("preflight endpoint path must start with '/'.")

    url = f"{settings.public_base_url}{path}"
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/json",
            "User-Agent": "muxivo-console-production-preflight/1",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=settings.timeout_seconds) as response:
            status = int(response.status)
            headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            response.read(8192)
            return status, headers
    except HTTPError as error:
        raise OSError(f"endpoint returned HTTP {error.code}") from error
    except URLError as error:
        raise OSError("endpoint transport failed") from error


def validate_public_http_surface(
    settings: NetworkPreflightSettings,
    *,
    http_getter: HttpGetter = fetch_http,
) -> None:
    """Require the frontend and API health endpoints to be publicly reachable."""
    endpoint_statuses: dict[str, int] = {}
    header_sets: dict[str, Mapping[str, str]] = {}

    for stage, path in (
        ("frontend", "/"),
        ("healthz", "/healthz"),
        ("readyz", "/readyz"),
    ):
        logger.info(
            "production_preflight.stage_started stage=%s path=%s",
            stage,
            path,
            extra={"stage": stage, "path": path},
        )
        status, headers = http_getter(settings, path)
        endpoint_statuses[stage] = status
        header_sets[stage] = headers
        if status != 200:
            raise OSError(f"{path} returned HTTP {status}")
        logger.info(
            "production_preflight.stage_succeeded stage=%s status=%s",
            stage,
            status,
            extra={"stage": stage, "status": status},
        )

    endpoints_missing_headers = {
        stage: sorted(
            header for header in REQUIRED_SECURITY_HEADERS if not headers.get(header, "").strip()
        )
        for stage, headers in header_sets.items()
        if any(not headers.get(header, "").strip() for header in REQUIRED_SECURITY_HEADERS)
    }
    if endpoints_missing_headers:
        raise OSError("public surface is missing required security headers")

    logger.info(
        "production_preflight.stage_succeeded "
        "stage=security_headers header_count=%s endpoint_count=%s",
        len(REQUIRED_SECURITY_HEADERS),
        len(endpoint_statuses),
        extra={
            "stage": "security_headers",
            "header_count": len(REQUIRED_SECURITY_HEADERS),
            "endpoint_count": len(endpoint_statuses),
        },
    )


def run_preflight(
    settings: NetworkPreflightSettings,
    *,
    dns_resolver: DnsResolver = socket.getaddrinfo,
    tls_validator: TlsValidator = validate_tls,
    http_getter: HttpGetter = fetch_http,
) -> tuple[str, ...]:
    """Run all read-only checks and return failed stage names."""
    failures: list[str] = []
    stages: tuple[tuple[str, Callable[[], None]], ...] = (
        ("dns", lambda: validate_dns(settings, resolver=dns_resolver)),
        ("tls", lambda: tls_validator(settings)),
        (
            "public_http_surface",
            lambda: validate_public_http_surface(settings, http_getter=http_getter),
        ),
    )

    for stage, check in stages:
        try:
            check()
        except Exception as error:  # pragma: no cover - exact transport errors vary by platform.
            logger.error(
                "production_preflight.stage_failed stage=%s error_type=%s",
                stage,
                type(error).__name__,
                extra={"stage": stage, "error_type": type(error).__name__},
            )
            failures.append(stage)

    return tuple(failures)


def main() -> int:
    """Run the production preflight without printing configuration values."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logger.info("production_preflight.started")
    try:
        settings = settings_from_environment()
    except ValueError as error:
        logger.error(
            "production_preflight.configuration_failed error_type=%s",
            type(error).__name__,
            extra={"error_type": type(error).__name__},
        )
        return 2

    failures = run_preflight(settings)
    if failures:
        logger.error(
            "production_preflight.failed failed_stage_count=%s failed_stages=%s",
            len(failures),
            ",".join(failures),
            extra={
                "failed_stage_count": len(failures),
                "failed_stages": ",".join(failures),
            },
        )
        return 1

    logger.info("production_preflight.completed")
    return 0


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be configured.")
    return value


def _parse_expected_dns_ips(value: str) -> frozenset[str]:
    addresses: set[str] = set()
    for raw_address in value.split(","):
        address = raw_address.strip()
        if not address:
            continue
        try:
            addresses.add(str(ipaddress.ip_address(address)))
        except ValueError as error:
            raise ValueError("MUXIVO_CONSOLE_EXPECTED_DNS_IPS contains an invalid IP.") from error
    if not addresses:
        raise ValueError("MUXIVO_CONSOLE_EXPECTED_DNS_IPS must contain an IP.")
    return frozenset(addresses)


def _parse_timeout(value: str) -> float:
    if not value:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(value)
    except ValueError as error:
        raise ValueError(
            "MUXIVO_CONSOLE_NETWORK_PREFLIGHT_TIMEOUT_SECONDS must be numeric."
        ) from error
    if not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(
            "MUXIVO_CONSOLE_NETWORK_PREFLIGHT_TIMEOUT_SECONDS must be between 0 and 60."
        )
    return timeout


if __name__ == "__main__":
    raise SystemExit(main())
