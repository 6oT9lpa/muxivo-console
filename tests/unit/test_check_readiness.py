import pytest
from muxivo_console.application.check_readiness import (
    CheckReadiness,
    NamedReadinessProbe,
    ReadinessStatus,
)


class Probe:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def check(self) -> None:
        self.calls += 1
        if self.error is not None:
            raise self.error


@pytest.mark.asyncio
async def test_reports_ready_only_when_every_required_probe_succeeds() -> None:
    database = Probe()
    migrations = Probe()
    use_case = CheckReadiness(
        [
            NamedReadinessProbe("database", database),
            NamedReadinessProbe("migrations", migrations),
        ]
    )

    report = await use_case.execute()

    assert report.status is ReadinessStatus.READY
    assert [component.status for component in report.components] == [
        ReadinessStatus.READY,
        ReadinessStatus.READY,
    ]
    assert database.calls == 1
    assert migrations.calls == 1


@pytest.mark.asyncio
async def test_dependency_failure_is_reduced_to_unavailable_without_error_details() -> None:
    database = Probe(RuntimeError("postgres password must never escape"))
    use_case = CheckReadiness([NamedReadinessProbe("database", database)])

    report = await use_case.execute()

    assert report.status is ReadinessStatus.UNAVAILABLE
    assert report.components[0].status is ReadinessStatus.UNAVAILABLE
    assert "password" not in repr(report)
