"""Run an actual development Docker Compose smoke test with ephemeral keys."""

from __future__ import annotations

import base64
import logging
import secrets
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("muxivo_console.development_composition_smoke")

DEFAULT_MAX_ATTEMPTS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 2.0
DEVELOPMENT_HEALTH_ENDPOINTS = ("/healthz", "/readyz")

CommandRunner = Callable[..., object]
HttpOpener = Callable[..., object]
Sleep = Callable[[float], None]


def development_environment_content() -> str:
    """Return a development-only environment with no committed secret values."""
    return "\n".join(
        (
            "MUXIVO_CONSOLE_ENVIRONMENT=development",
            "MUXIVO_CONSOLE_DATABASE_URL=postgresql+asyncpg://muxivo:muxivo@postgres:5432/muxivo_console",
            f"MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY={_base64_key()}",
            f"MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY={_fernet_key()}",
            f"MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER={_base64_key()}",
            "MUXIVO_DISCORD_CONTROL_BASE_URL=http://127.0.0.1:8030",
            f"MUXIVO_DISCORD_CONTROL_SIGNING_KEY={_base64_key()}",
            "",
        )
    )


def run_smoke(
    *,
    root: Path = Path("."),
    runner: CommandRunner = subprocess.run,
    opener: HttpOpener = urlopen,
    sleep: Sleep = time.sleep,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """Build, start and health-check the development composition, then stop it."""
    compose_file = root / "docker-compose.dev.yml"
    environment_file = root / ".dev" / "console.env"
    compose_command = ("docker", "compose", "-f", str(compose_file))

    if not compose_file.is_file():
        raise FileNotFoundError(f"Docker Compose file is missing: {compose_file}")
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
            (*compose_command, "up", "-d", "--build", "--wait", "postgres", "api"),
            root=root,
            stage="startup",
        )
        _wait_for_health(
            opener=opener,
            sleep=sleep,
            max_attempts=max_attempts,
        )
        logger.info(
            "development_composition_smoke.completed",
            extra={"endpoint_count": len(DEVELOPMENT_HEALTH_ENDPOINTS)},
        )
    finally:
        logger.info("development_composition_smoke.cleanup_started")
        _run_cleanup(runner, (*compose_command, "down", "--remove-orphans"), root=root)
        if environment_was_created:
            environment_file.unlink(missing_ok=True)
            logger.info("development_composition_smoke.generated_environment_removed")
        logger.info("development_composition_smoke.cleanup_completed")


def _ensure_environment_file(path: Path) -> bool:
    if path.exists():
        logger.info(
            "development_composition_smoke.environment_reused",
            extra={"environment_path": str(path)},
        )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(development_environment_content(), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        logger.debug("development_composition_smoke.environment_mode_unavailable")
    logger.info(
        "development_composition_smoke.generated_environment_created",
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
    logger.info(
        "development_composition_smoke.stage_started",
        extra={"stage": stage},
    )
    # Compose renders the complete environment in `config`; capture every
    # command so generated credentials never reach the terminal or CI logs.
    try:
        runner(command, check=True, cwd=str(root), capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        logger.error(
            "development_composition_smoke.stage_failed",
            extra={
                "stage": stage,
                "error_type": type(error).__name__,
                "return_code": error.returncode,
            },
        )
        raise
    except OSError as error:
        logger.error(
            "development_composition_smoke.stage_failed",
            extra={
                "stage": stage,
                "error_type": type(error).__name__,
                "errno": error.errno,
            },
        )
        raise
    logger.info(
        "development_composition_smoke.stage_completed",
        extra={"stage": stage},
    )


def _run_cleanup(runner: CommandRunner, command: Sequence[str], *, root: Path) -> None:
    try:
        runner(
            command,
            check=False,
            cwd=str(root),
            capture_output=True,
            text=True,
        )
    except Exception as error:  # pragma: no cover - depends on local Docker behavior.
        logger.error(
            "development_composition_smoke.cleanup_failed",
            extra={"error_type": type(error).__name__},
        )


def _wait_for_health(
    *,
    opener: HttpOpener,
    sleep: Sleep,
    max_attempts: int,
) -> None:
    for attempt in range(1, max_attempts + 1):
        statuses: dict[str, int] = {}
        try:
            for endpoint in DEVELOPMENT_HEALTH_ENDPOINTS:
                statuses[endpoint] = _get_status(opener, endpoint)
            if all(status == 200 for status in statuses.values()):
                logger.info(
                    "development_composition_smoke.health_succeeded",
                    extra={"attempt": attempt, "endpoint_count": len(statuses)},
                )
                return
        except (OSError, URLError):
            statuses = {}
        logger.info(
            "development_composition_smoke.health_pending",
            extra={"attempt": attempt, "max_attempts": max_attempts},
        )
        sleep(DEFAULT_POLL_INTERVAL_SECONDS)
    raise TimeoutError("Development Console composition did not become healthy.")


def _get_status(opener: HttpOpener, endpoint: str) -> int:
    request = Request(
        f"http://127.0.0.1:8000{endpoint}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with opener(request, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as response:
        return int(response.status)


def _base64_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def _fernet_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def main() -> int:
    """Return a non-zero status when the real development composition fails."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        run_smoke()
    except Exception as error:
        logger.error(
            "development_composition_smoke.failed",
            extra={"error_type": type(error).__name__},
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
