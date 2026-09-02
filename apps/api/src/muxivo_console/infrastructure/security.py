"""Compatibility facade for the Console's security adapters.

Concrete adapters live in one-class modules. This facade preserves the original
imports used by the composition root and existing integrations.
"""

from muxivo_console.infrastructure.argon2id_password_hasher import Argon2idPasswordHasher
from muxivo_console.infrastructure.fernet_email_protector import FernetEmailProtector
from muxivo_console.infrastructure.fernet_opaque_value_protector import (
    FernetOpaqueValueProtector,
)
from muxivo_console.infrastructure.hmac_email_lookup_hasher import HmacEmailLookupHasher
from muxivo_console.infrastructure.hmac_session_token_hasher import HmacSessionTokenHasher
from muxivo_console.infrastructure.secure_opaque_session_token_issuer import (
    SecureOpaqueSessionTokenIssuer,
)
from muxivo_console.infrastructure.utc_clock import UtcClock
from muxivo_console.infrastructure.uuid7_identifier_generator import Uuid7IdentifierGenerator
from muxivo_console.infrastructure.validated_email_address_normalizer import (
    ValidatedEmailAddressNormalizer,
)

__all__ = [
    "Argon2idPasswordHasher",
    "FernetEmailProtector",
    "FernetOpaqueValueProtector",
    "HmacEmailLookupHasher",
    "HmacSessionTokenHasher",
    "SecureOpaqueSessionTokenIssuer",
    "UtcClock",
    "Uuid7IdentifierGenerator",
    "ValidatedEmailAddressNormalizer",
]
