import logging
from uuid import UUID

from fastapi.testclient import TestClient
from muxivo_console.presentation.api import create_app


class ReadinessProbe:
    def __init__(self, ready: bool) -> None:
        self.ready = ready
        self.correlation_ids: list[UUID] = []

    async def check(self, *, correlation_id: UUID) -> bool:
        self.correlation_ids.append(correlation_id)
        return self.ready


class FailingReadinessProbe:
    async def check(self, **_: object) -> bool:
        raise RuntimeError("database password=should-not-be-public")


def test_readyz_returns_ok_only_when_composed_probe_is_ready() -> None:
    probe = ReadinessProbe(ready=True)
    client = TestClient(create_app(readiness_probe=probe))

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(probe.correlation_ids) == 1
    assert response.headers["X-Correlation-ID"] == str(probe.correlation_ids[0])


def test_readyz_fails_closed_when_probe_reports_not_ready() -> None:
    client = TestClient(create_app(readiness_probe=ReadinessProbe(ready=False)))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}


def test_readyz_is_unavailable_without_explicit_runtime_probe() -> None:
    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Readiness is unavailable"}


def test_readyz_hides_probe_failures_from_response_and_logs(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="muxivo_console.presentation.api")
    client = TestClient(create_app(readiness_probe=FailingReadinessProbe()))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert "should-not-be-public" not in response.text
    assert "should-not-be-public" not in caplog.text
    assert "operations.readiness.check_failed" in caplog.text
