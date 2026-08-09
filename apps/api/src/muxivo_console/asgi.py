"""Production ASGI entrypoint.

Run with ``uvicorn muxivo_console.asgi:app``. Importing this module is
deliberately fail-fast: deployments must provide every security-critical
setting before the API can accept browser traffic.
"""

from muxivo_console.infrastructure.composition import create_production_app
from muxivo_console.infrastructure.settings import ConsoleSettings

app = create_production_app(ConsoleSettings.from_environment())
