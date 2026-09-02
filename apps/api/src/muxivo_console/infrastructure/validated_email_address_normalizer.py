"""Validated email address normalization adapter."""

from email_validator import EmailNotValidError, validate_email


class ValidatedEmailAddressNormalizer:
    """Normalize user email addresses without performing deliverability probes."""

    def normalize(self, value: str) -> str:
        try:
            return validate_email(value, check_deliverability=False).normalized
        except EmailNotValidError as error:
            raise ValueError("Email address is invalid.") from error
