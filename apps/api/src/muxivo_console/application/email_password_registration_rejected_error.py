"""Domain-level rejection for verified e-mail/password account creation."""

from __future__ import annotations


class EmailPasswordRegistrationRejectedError(ValueError):
    """Signal a generic account-creation conflict without enumeration details."""
