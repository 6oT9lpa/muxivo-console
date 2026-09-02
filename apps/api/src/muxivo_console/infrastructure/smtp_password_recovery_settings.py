"""SMTP configuration value object used by recovery and invitations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SmtpPasswordRecoverySettings:
    """Validated, optionally authenticated SMTP relay settings."""

    host: str
    port: int
    from_email: str
    reset_url_base: str
    invitation_url_base: str | None = None
    username: str | None = None
    password: str | None = None
    starttls: bool = True
