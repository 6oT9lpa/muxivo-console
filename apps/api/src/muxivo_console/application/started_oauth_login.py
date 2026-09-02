"""One-time OAuth login initiation response."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StartedOAuthLogin:
    """Return the browser challenge while excluding state from representations."""

    state: str = field(repr=False)
    code_challenge: str
    expires_in_seconds: int
