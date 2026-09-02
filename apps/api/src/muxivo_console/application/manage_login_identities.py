"""Compatibility exports for authenticated login identity management.

Concrete classes are intentionally isolated so each module has one class and
the existing application import surface remains stable.
"""

from muxivo_console.application.list_login_identities import ListLoginIdentities
from muxivo_console.application.list_login_identities_command import ListLoginIdentitiesCommand
from muxivo_console.application.login_identity_management_error import (
    LoginIdentityManagementRejectedError,
)
from muxivo_console.application.unlink_login_identity import UnlinkLoginIdentity
from muxivo_console.application.unlink_login_identity_command import UnlinkLoginIdentityCommand

__all__ = [
    "ListLoginIdentities",
    "ListLoginIdentitiesCommand",
    "LoginIdentityManagementRejectedError",
    "UnlinkLoginIdentity",
    "UnlinkLoginIdentityCommand",
]
