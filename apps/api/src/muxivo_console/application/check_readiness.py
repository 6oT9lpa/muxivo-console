"""Deployment readiness orchestration with infrastructure hidden behind probes."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ReadinessStatus(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"


class ReadinessProbe(Protocol):
    """Raises or returns normally depending on one required dependency."""

    async def check(self) -> None: ...


@dataclass(frozen=True, slots=True)
class NamedReadinessProbe:
    name: str
    probe: ReadinessProbe

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Readiness probe name must not be blank.")


@dataclass(frozen=True, slots=True)
class ReadinessComponent:
    name: str
    status: ReadinessStatus


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    status: ReadinessStatus
    components: tuple[ReadinessComponent, ...]


@dataclass(slots=True)
class CheckReadiness:
    probes: Sequence[NamedReadinessProbe]

    async def execute(self) -> ReadinessReport:
        components: list[ReadinessComponent] = []
        for registered in self.probes:
            try:
                await registered.probe.check()
            except Exception:
                status = ReadinessStatus.UNAVAILABLE
            else:
                status = ReadinessStatus.READY
            components.append(ReadinessComponent(registered.name, status))
        overall = (
            ReadinessStatus.READY
            if all(component.status is ReadinessStatus.READY for component in components)
            else ReadinessStatus.UNAVAILABLE
        )
        return ReadinessReport(overall, tuple(components))
