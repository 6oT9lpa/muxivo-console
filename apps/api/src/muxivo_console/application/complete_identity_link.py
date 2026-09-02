"""Compatibility exports for completing an external identity link."""

from muxivo_console.application.complete_identity_link_command import CompleteIdentityLinkCommand
from muxivo_console.application.complete_identity_link_use_case import CompleteIdentityLink
from muxivo_console.application.identity_link_completion_error import (
    IdentityLinkCompletionRejectedError,
)

__all__ = [
    "CompleteIdentityLink",
    "CompleteIdentityLinkCommand",
    "IdentityLinkCompletionRejectedError",
]
