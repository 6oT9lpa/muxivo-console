"""Server-controlled naming adapters."""

import re
import secrets
import unicodedata


class RandomSuffixOrganizationSlugGenerator:
    """Generate a readable slug with server entropy to avoid tenant collisions."""

    def generate(self, organization_name: str) -> str:
        normalized = unicodedata.normalize("NFKD", organization_name)
        ascii_name = normalized.encode("ascii", "ignore").decode().lower()
        stem = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "organization"
        suffix = secrets.token_hex(4)
        return f"{stem[: 96 - len(suffix) - 1].rstrip('-')}-{suffix}"
