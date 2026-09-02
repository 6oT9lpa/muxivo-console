"""Compatibility exports for linking verified provider identities."""

from muxivo_console.application.identity_link_error import IdentityLinkRejectedError
from muxivo_console.application.link_verified_identity_command import LinkVerifiedIdentityCommand
from muxivo_console.application.link_verified_identity_use_case import LinkVerifiedIdentity

__all__ = ["IdentityLinkRejectedError", "LinkVerifiedIdentity", "LinkVerifiedIdentityCommand"]
