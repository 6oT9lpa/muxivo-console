"""Explicit localhost-only ASGI entrypoint.

Run with ``uvicorn muxivo_console.asgi_development:app``. This module rejects
any environment other than ``development`` and uses non-Secure cookie names
solely because localhost HTTP cannot accept production ``__Host-`` cookies.
"""

from muxivo_console.infrastructure.composition import create_development_app
from muxivo_console.infrastructure.settings import ConsoleSettings

app = create_development_app(ConsoleSettings.from_environment())
