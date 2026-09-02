"""One-time OAuth link initiation response."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StartedIdentityLink:
    """Return the browser challenge while excluding state from representations."""

    state: str = field(repr=False)
    code_challenge: str
    expires_in_seconds: int
