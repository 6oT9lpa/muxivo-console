from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from scripts.development_composition_smoke import (
    development_environment_content,
    run_smoke,
)


def test_development_environment_generates_all_required_runtime_values() -> None:
    environment = development_environment_content()
    values = dict(line.split("=", maxsplit=1) for line in environment.splitlines() if line)

    assert values["MUXIVO_CONSOLE_ENVIRONMENT"] == "development"
    assert values["MUXIVO_CONSOLE_DATABASE_URL"].endswith("@postgres:5432/muxivo_console")
    assert len(values["MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY"]) >= 44
    assert len(values["MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY"]) == 44
    assert len(values["MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER"]) >= 44
    assert values["MUXIVO_DISCORD_CONTROL_BASE_URL"].startswith("http://")
    assert len(values["MUXIVO_DISCORD_CONTROL_SIGNING_KEY"]) >= 44


def test_smoke_runs_real_compose_stages_and_cleans_generated_environment(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.dev.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    commands: list[tuple[tuple[str, ...], bool]] = []

    def runner(command, *, check, cwd):
        commands.append((tuple(command), check))

    def opener(request, *, timeout):
        assert request.full_url in {
            "http://127.0.0.1:8000/healthz",
            "http://127.0.0.1:8000/readyz",
        }
        assert timeout > 0
        return nullcontext(SimpleNamespace(status=200))

    run_smoke(
        root=tmp_path,
        runner=runner,
        opener=opener,
        sleep=lambda _: None,
        max_attempts=1,
    )

    assert commands[0][0][-1] == "config"
    assert commands[1][0][-6:] == ("up", "-d", "--build", "--wait", "postgres", "api")
    assert commands[-1][0][-2:] == ("down", "--remove-orphans")
    assert commands[-1][1] is False
    assert not (tmp_path / ".dev" / "console.env").exists()


def test_smoke_preserves_existing_development_environment(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.dev.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    environment_file = tmp_path / ".dev" / "console.env"
    environment_file.parent.mkdir()
    environment_file.write_text("existing=true\n", encoding="utf-8")

    run_smoke(
        root=tmp_path,
        runner=lambda *_args, **_kwargs: None,
        opener=lambda *_args, **_kwargs: nullcontext(SimpleNamespace(status=200)),
        sleep=lambda _: None,
        max_attempts=1,
    )

    assert environment_file.read_text(encoding="utf-8") == "existing=true\n"
