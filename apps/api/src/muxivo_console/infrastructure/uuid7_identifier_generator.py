"""UUIDv7 identifier generation adapter."""

import secrets
import time
from uuid import UUID


class Uuid7IdentifierGenerator:
    """Generate RFC 9562 UUIDv7 values without client control over identifiers."""

    def new(self) -> UUID:
        timestamp_ms = int(time.time() * 1000)
        random_bits = secrets.randbits(74)
        value = (timestamp_ms << 80) | (0b0111 << 76) | (random_bits & ((1 << 76) - 1))
        value = (value & ~(0b11 << 62)) | (0b10 << 62)
        return UUID(int=value)
