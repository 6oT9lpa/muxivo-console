"""Result returned after starting or resending e-mail verification."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailPasswordRegistrationVerificationResult:
    """Expose only the opaque pending-flow token and its lifetime to the browser."""

    raw_token: str | None
    expires_in_seconds: int
