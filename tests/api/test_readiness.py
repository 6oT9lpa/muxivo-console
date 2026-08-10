from fastapi.testclient import TestClient
from muxivo_console.application.check_readiness import (
    ReadinessComponent,
    ReadinessReport,
    ReadinessStatus,
)
from muxivo_console.presentation.api import create_app
from muxivo_console.presentation.operations import create_operations_router


class ReadinessUseCase:
    def __init__(self, report: ReadinessReport) -> None:
        self.report = report
        self.calls = 0

    async def execute(self) -> ReadinessReport:
        self.calls += 1
        return self.report


def client_for(report: ReadinessReport) -> tuple[TestClient, ReadinessUseCase]:
    use_case = ReadinessUseCase(report)
    app = create_app()
    app.include_router(create_operations_router(use_case))
    return TestClient(app), use_case


def test_readyz_returns_success_when_required_dependencies_are_ready() -> None:
    client, use_case = client_for(
        ReadinessReport(
            ReadinessStatus.READY,
            (ReadinessComponent("database", ReadinessStatus.READY),),
        )
    )

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "components": [{"name": "database", "status": "ready"}],
    }
    assert use_case.calls == 1


def test_readyz_returns_service_unavailable_without_dependency_error_details() -> None:
    client, _ = client_for(
        ReadinessReport(
            ReadinessStatus.UNAVAILABLE,
            (ReadinessComponent("database", ReadinessStatus.UNAVAILABLE),),
        )
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "components": [{"name": "database", "status": "unavailable"}],
    }
    assert "postgres" not in response.text.lower()
