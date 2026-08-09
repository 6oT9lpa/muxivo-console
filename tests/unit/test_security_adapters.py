from muxivo_console.infrastructure.security import (
    Argon2idPasswordHasher,
    HmacSessionTokenHasher,
    SecureOpaqueSessionTokenIssuer,
    Uuid7IdentifierGenerator,
)


def test_argon2id_hasher_never_persists_a_plaintext_password() -> None:
    hasher = Argon2idPasswordHasher()

    encoded = hasher.hash("a-safe-test-password")

    assert encoded.startswith("$argon2id$")
    assert "a-safe-test-password" not in encoded
    assert hasher.verify(encoded, "a-safe-test-password") is True
    assert hasher.verify(encoded, "another-password") is False


def test_uuid7_identifier_generator_sets_version_and_variant_bits() -> None:
    identifier = Uuid7IdentifierGenerator().new()

    assert identifier.version == 7
    assert identifier.variant == "specified in RFC 4122"


def test_session_tokens_are_opaque_and_persisted_as_keyed_hashes() -> None:
    raw_token = SecureOpaqueSessionTokenIssuer().issue()
    hasher = HmacSessionTokenHasher(b"p" * 32)

    token_hash = hasher.hash(raw_token)

    assert len(raw_token) >= 43
    assert len(token_hash) == 64
    assert raw_token not in token_hash
    assert hasher.hash(raw_token) == token_hash
