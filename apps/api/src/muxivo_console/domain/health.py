"""Platform-neutral, aggregate health facts shown in Muxivo Console."""

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class HealthStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class HealthSignal:
    key: str
    display_name: str
    value: str
    status: HealthStatus
    latency_ms: int | None

    def __post_init__(self) -> None:
        if not self.key or not self.display_name.strip() or not self.value.strip():
            raise ValueError("Health signal fields must be non-empty.")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("Health signal latency must not be negative.")


@dataclass(frozen=True, slots=True)
class PlatformHealth:
    platform: Platform
    signals: tuple[HealthSignal, ...]
