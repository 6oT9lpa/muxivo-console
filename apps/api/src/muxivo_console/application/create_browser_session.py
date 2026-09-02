"""Compatibility exports for browser session creation.

Concrete session classes and data contracts are isolated into one-class modules
while existing imports remain stable for the API and infrastructure layers.
"""

from muxivo_console.application.create_browser_session_command import CreateBrowserSessionCommand
from muxivo_console.application.create_browser_session_use_case import CreateBrowserSession
from muxivo_console.application.issued_browser_session import IssuedBrowserSession
from muxivo_console.application.session_creation_error import SessionCreationRejectedError

__all__ = [
    "CreateBrowserSession",
    "CreateBrowserSessionCommand",
    "IssuedBrowserSession",
    "SessionCreationRejectedError",
]
