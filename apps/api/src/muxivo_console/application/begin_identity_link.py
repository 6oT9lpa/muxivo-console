"""Compatibility exports for starting an external identity link."""

from muxivo_console.application.begin_identity_link_command import BeginIdentityLinkCommand
from muxivo_console.application.begin_identity_link_use_case import BeginIdentityLink
from muxivo_console.application.identity_link_start_error import IdentityLinkStartRejectedError
from muxivo_console.application.started_identity_link import StartedIdentityLink

__all__ = [
    "BeginIdentityLink",
    "BeginIdentityLinkCommand",
    "IdentityLinkStartRejectedError",
    "StartedIdentityLink",
]
