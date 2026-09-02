from fastapi.testclient import TestClient
from muxivo_console.infrastructure.metrics import InMemoryHttpMetricsRecorder
from muxivo_console.presentation.api import create_app


def test_metrics_endpoint_exposes_recorded_http_requests() -> None:
    recorder = InMemoryHttpMetricsRecorder()
    client = TestClient(create_app(metrics_recorder=recorder))

    health_response = client.get("/healthz")
    metrics_response = client.get("/metrics")

    assert health_response.status_code == 200
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")
    assert "muxivo_console_http_requests_total" in metrics_response.text
    assert 'method="GET",route="/healthz",status_code="200"' in metrics_response.text


def test_metrics_endpoint_reports_unavailable_when_not_configured() -> None:
    client = TestClient(create_app())

    response = client.get("/metrics")

    assert response.status_code == 503
    assert response.json() == {"detail": "Metrics are unavailable"}
