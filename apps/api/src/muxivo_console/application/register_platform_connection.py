"""Compatibility exports for platform connection registration."""

from muxivo_console.application.platform_connection_registration_error import (
    PlatformConnectionRegistrationRejectedError,
)
from muxivo_console.application.platform_connection_verifier_router import (
    PlatformConnectionVerifierRouter,
)
from muxivo_console.application.register_platform_connection_command import (
    RegisterPlatformConnectionCommand,
)
from muxivo_console.application.register_platform_connection_use_case import (
    RegisterPlatformConnection,
)

__all__ = [
    "PlatformConnectionRegistrationRejectedError",
    "PlatformConnectionVerifierRouter",
    "RegisterPlatformConnection",
    "RegisterPlatformConnectionCommand",
]
