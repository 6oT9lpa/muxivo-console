"""Aggregate returned by a platform Control API candidate discovery call."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.platform_connection_candidate import PlatformConnectionCandidate


@dataclass(frozen=True, slots=True)
class PlatformConnectionCandidateCatalog:
    """Resources available to the linked platform identity for one organization."""

    platform: Platform
    items: tuple[PlatformConnectionCandidate, ...]
    identity_linked: bool

    def __post_init__(self) -> None:
        if not isinstance(self.identity_linked, bool):
            raise ValueError("Candidate catalog identity state must be boolean.")
        if not self.identity_linked and self.items:
            raise ValueError("An unlinked identity cannot have connection candidates.")
        if any(candidate.platform is not self.platform for candidate in self.items):
            raise ValueError("All candidates must belong to the catalog platform.")
        resource_ids = [candidate.external_resource_id for candidate in self.items]
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("Candidate resource identifiers must be unique.")
