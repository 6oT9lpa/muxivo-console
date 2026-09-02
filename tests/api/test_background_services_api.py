from fastapi.testclient import TestClient
from muxivo_console.presentation.api import create_app


class BackgroundService:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1


def test_app_lifespan_starts_and_stops_background_services() -> None:
    service = BackgroundService()
    app = create_app(background_services=(service,))

    with TestClient(app) as client:
        assert service.started == 1
        assert service.stopped == 0
        assert client.get("/healthz").status_code == 200

    assert service.started == 1
    assert service.stopped == 1
