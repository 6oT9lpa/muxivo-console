"""Platform adapter capabilities configured in the Console control plane."""

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class PlatformAdapterCapability(StrEnum):
    CONNECTION_REGISTRATION = "connection_registration"
    CONTROL_MODULES = "control_modules"
    HEALTH = "health"
    DASHBOARD_SUMMARY = "dashboard_summary"
    SERVER_STATS = "server_stats"


@dataclass(frozen=True, slots=True)
class PlatformAdapterDescriptor:
    """Infrastructure capability, not an authorization grant for a user or tenant."""

    platform: Platform
    capabilities: frozenset[PlatformAdapterCapability]
