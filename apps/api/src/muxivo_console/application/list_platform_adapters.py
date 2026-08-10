"""Describe platform adapters configured in the running Console deployment."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from muxivo_console.domain.platforms import PlatformAdapterDescriptor


class PlatformAdapterCatalog(Protocol):
    """Read configured adapter capabilities without granting tenant authorization."""

    def list_configured(self) -> Sequence[PlatformAdapterDescriptor]: ...


@dataclass(slots=True)
class ListPlatformAdapters:
    catalog: PlatformAdapterCatalog

    def execute(self) -> tuple[PlatformAdapterDescriptor, ...]:
        return tuple(self.catalog.list_configured())
