import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from scripts.observability_composition_smoke import run_smoke


def test_observability_smoke_runs_compose_and_verifies_prometheus_contract(
    tmp_path: Path,
) -> None:
    (tmp_path / "docker-compose.dev.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "docker-compose.observability.dev.yml").write_text(
        "services: {}\n", encoding="utf-8"
    )
    commands: list[tuple[tuple[str, ...], bool]] = []

    configuration = {"status": "success", "data": {"yaml": "scrape_configs:"}}
    rules = {"status": "success", "data": {"groups": [{"name": "console"}]}}
    targets = {
        "status": "success",
        "data": {
            "activeTargets": [
                {"health": "up", "labels": {"job": "muxivo-console"}},
            ]
        },
    }

    def runner(command, *, check, cwd, capture_output, text):
        commands.append((tuple(command), check))

    def opener(request, *, timeout):
        if request.full_url.endswith("/-/ready") or request.full_url.endswith("/-/healthy"):
            return nullcontext(SimpleNamespace(status=200))
        payload = (
            configuration
            if request.full_url.endswith("/status/config")
            else rules
            if request.full_url.endswith("/api/v1/rules")
            else targets
        )
        return nullcontext(
            SimpleNamespace(status=200, read=lambda: json.dumps(payload).encode("utf-8"))
        )

    run_smoke(
        root=tmp_path,
        runner=runner,
        opener=opener,
        sleep=lambda _: None,
        max_attempts=1,
    )

    assert commands[0][0][-1] == "config"
    assert commands[1][0][-5:] == (
        "--wait",
        "postgres",
        "redis",
        "api",
        "prometheus",
    )
    assert commands[-1][0][-2:] == ("down", "--remove-orphans")
    assert commands[-1][1] is False
    assert not (tmp_path / ".dev" / "console.env").exists()


def test_observability_smoke_preserves_an_existing_environment_file(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.dev.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "docker-compose.observability.dev.yml").write_text(
        "services: {}\n", encoding="utf-8"
    )
    environment_file = tmp_path / ".dev" / "console.env"
    environment_file.parent.mkdir()
    environment_file.write_text("existing=true\n", encoding="utf-8")

    def opener(request, *, timeout):
        if request.full_url.endswith("/-/ready") or request.full_url.endswith("/-/healthy"):
            return nullcontext(SimpleNamespace(status=200))
        payload = {
            "status": "success",
            "data": {
                "groups": [{"name": "console"}],
                "activeTargets": [
                    {"health": "up", "labels": {"job": "muxivo-console"}},
                ],
            },
        }
        return nullcontext(
            SimpleNamespace(status=200, read=lambda: json.dumps(payload).encode("utf-8"))
        )

    run_smoke(
        root=tmp_path,
        runner=lambda *_args, **_kwargs: None,
        opener=opener,
        sleep=lambda _: None,
        max_attempts=1,
    )

    assert environment_file.read_text(encoding="utf-8") == "existing=true\n"
