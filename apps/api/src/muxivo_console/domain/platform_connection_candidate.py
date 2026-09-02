"""Safe platform resources that can be selected during connection setup."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformConnectionCandidate:
    """A platform-owned resource exposed without credentials or opaque tokens."""

    platform: Platform
    external_resource_id: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.external_resource_id.strip() or len(self.external_resource_id) > 255:
            raise ValueError("External resource identifier must contain 1 to 255 characters.")
        if not self.display_name.strip() or len(self.display_name) > 255:
            raise ValueError("Candidate display name must contain 1 to 255 characters.")
