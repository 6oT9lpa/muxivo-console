"""Run a real development API and Prometheus composition smoke test."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from scripts.development_composition_smoke import development_environment_content

logger = logging.getLogger("muxivo_console.observability_composition_smoke")

DEFAULT_MAX_ATTEMPTS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 2.0
COMPOSE_PROJECT_NAME = "muxivo-console-observability-smoke"
PROMETHEUS_ENDPOINTS = (
    "http://127.0.0.1:9090/-/ready",
    "http://127.0.0.1:9090/-/healthy",
)

CommandRunner = Callable[..., object]
HttpOpener = Callable[..., object]
Sleep = Callable[[float], None]


def run_smoke(
    *,
    root: Path = Path("."),
    runner: CommandRunner = subprocess.run,
    opener: HttpOpener = urlopen,
    sleep: Sleep = time.sleep,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """Start the development observability composition and verify its contract."""
    development_compose = root / "docker-compose.dev.yml"
    observability_compose = root / "docker-compose.observability.dev.yml"
    environment_file = root / ".dev" / "console.env"
    compose_command = (
        "docker",
        "compose",
        "--project-name",
        COMPOSE_PROJECT_NAME,
        "-f",
        str(development_compose),
        "-f",
        str(observability_compose),
    )

    if not development_compose.is_file():
        raise FileNotFoundError(f"Development Compose file is missing: {development_compose}")
    if not observability_compose.is_file():
        raise FileNotFoundError(f"Observability Compose file is missing: {observability_compose}")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    environment_was_created = _ensure_environment_file(environment_file)
    try:
        _run_command(
            runner,
            (*compose_command, "config"),
            root=root,
            stage="configuration",
        )
        _run_command(
            runner,
            (
                *compose_command,
                "up",
                "-d",
                "--build",
                "--wait",
                "postgres",
                "redis",
                "api",
                "prometheus",
            ),
            root=root,
            stage="startup",
        )
        _wait_for_prometheus(
            opener=opener,
            sleep=sleep,
            max_attempts=max_attempts,
        )
        logger.info(
            "observability_composition_smoke.completed",
            extra={"prometheus_endpoint_count": len(PROMETHEUS_ENDPOINTS)},
        )
    finally:
        logger.info("observability_composition_smoke.cleanup_started")
        _run_cleanup(
            runner,
            (*compose_command, "down", "--remove-orphans"),
            root=root,
        )
        if environment_was_created:
            environment_file.unlink(missing_ok=True)
            logger.info("observability_composition_smoke.generated_environment_removed")
        logger.info("observability_composition_smoke.cleanup_completed")


def _ensure_environment_file(path: Path) -> bool:
    if path.exists():
        logger.info(
            "observability_composition_smoke.environment_reused",
            extra={"environment_path": str(path)},
        )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(development_environment_content(), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        logger.debug("observability_composition_smoke.environment_mode_unavailable")
    logger.info(
        "observability_composition_smoke.generated_environment_created",
        extra={"environment_path": str(path)},
    )
    return True


def _run_command(
    runner: CommandRunner,
    command: Sequence[str],
    *,
    root: Path,
    stage: str,
) -> None:
    logger.info("observability_composition_smoke.stage_started", extra={"stage": stage})
    try:
        runner(command, check=True, cwd=str(root), capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        logger.error(
            "observability_composition_smoke.stage_failed",
            extra={
                "stage": stage,
                "error_type": type(error).__name__,
                "return_code": error.returncode,
            },
        )
        raise
    except OSError as error:
        logger.error(
            "observability_composition_smoke.stage_failed",
            extra={
                "stage": stage,
                "error_type": type(error).__name__,
                "errno": error.errno,
            },
        )
        raise
    logger.info("observability_composition_smoke.stage_completed", extra={"stage": stage})


def _run_cleanup(runner: CommandRunner, command: Sequence[str], *, root: Path) -> None:
    try:
        runner(
            command,
            check=False,
            cwd=str(root),
            capture_output=True,
            text=True,
        )
    except Exception as error:  # pragma: no cover - Docker behavior is environment-specific.
        logger.error(
            "observability_composition_smoke.cleanup_failed",
            extra={"error_type": type(error).__name__},
        )


def _wait_for_prometheus(
    *,
    opener: HttpOpener,
    sleep: Sleep,
    max_attempts: int,
) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            statuses = {
                endpoint: _get_status(opener, endpoint) for endpoint in PROMETHEUS_ENDPOINTS
            }
            configuration = _get_json(
                opener,
                "http://127.0.0.1:9090/api/v1/status/config",
            )
            rules = _get_json(opener, "http://127.0.0.1:9090/api/v1/rules")
            targets = _get_json(opener, "http://127.0.0.1:9090/api/v1/targets")
            if (
                all(status == 200 for status in statuses.values())
                and _prometheus_api_succeeded(configuration)
                and _prometheus_api_succeeded(rules)
                and _has_healthy_console_target(targets)
                and _has_loaded_rule_group(rules)
            ):
                logger.info(
                    "observability_composition_smoke.health_succeeded",
                    extra={"attempt": attempt},
                )
                return
        except (OSError, URLError, ValueError, TypeError, KeyError):
            pass
        logger.info(
            "observability_composition_smoke.health_pending",
            extra={"attempt": attempt, "max_attempts": max_attempts},
        )
        sleep(DEFAULT_POLL_INTERVAL_SECONDS)
    raise TimeoutError("Development observability composition did not become healthy.")


def _get_status(opener: HttpOpener, url: str) -> int:
    request = Request(url, headers={"Accept": "text/plain"}, method="GET")
    with opener(request, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as response:
        return int(response.status)


def _get_json(opener: HttpOpener, url: str) -> object:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with opener(request, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as response:
        if int(response.status) != 200:
            raise ValueError("Prometheus API request failed")
        return json.loads(response.read().decode("utf-8"))


def _prometheus_api_succeeded(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("status") == "success"


def _has_loaded_rule_group(payload: object) -> bool:
    if not isinstance(payload, dict) or not _prometheus_api_succeeded(payload):
        return False
    data = payload.get("data")
    return isinstance(data, dict) and bool(data.get("groups"))


def _has_healthy_console_target(payload: object) -> bool:
    if not isinstance(payload, dict) or not _prometheus_api_succeeded(payload):
        return False
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("activeTargets"), list):
        return False
    return any(
        isinstance(target, dict)
        and target.get("health") == "up"
        and isinstance(target.get("labels"), dict)
        and target["labels"].get("job") == "muxivo-console"
        for target in data["activeTargets"]
    )


def main() -> int:
    """Return a non-zero status when the observability composition fails."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        run_smoke()
    except Exception as error:
        logger.error(
            "observability_composition_smoke.failed",
            extra={"error_type": type(error).__name__},
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
