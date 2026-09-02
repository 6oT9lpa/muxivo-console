"""Validate that Console Foundation production-readiness artifacts stay complete.

The roadmap requires several non-code launch artifacts before staging/public
production. This checker turns those documents and CI gates into a regression
guard: if a future edit removes a required section, command or operational
checklist item, CI fails with an actionable message.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReadinessArtifactIssue:
    artifact: Path
    marker: str
    reason: str


REQUIRED_READINESS_MARKERS: tuple[tuple[str, str], ...] = (
    ("# Muxivo Console production readiness", "document title"),
    ("## Launch gates", "launch gate table"),
    ("## Privacy policy draft outline", "privacy policy draft"),
    ("## Terms draft outline", "terms draft"),
    ("## Data inventory", "data inventory"),
    ("## Retention policy draft", "retention policy"),
    ("## Revoke/delete request procedure", "revoke/delete procedure"),
    ("## Incident runbook", "incident runbook"),
    ("## Alerting plan", "alerting plan"),
    ("## Domain and OAuth checklist", "staging/prod domain and OAuth checklist"),
    ("## KMS/secret manager decision", "secret manager decision"),
    ("## Backup/restore drill", "backup/restore drill"),
)

REQUIRED_LAUNCH_GATES: tuple[tuple[str, str], ...] = (
    ("Password recovery SMTP delivery adapter configured outside logs", "password recovery gate"),
    (
        (
            "Shared rate limits enabled for login, registration, reauthentication, "
            "OAuth callback and recovery"
        ),
        "rate-limit gate",
    ),
    ("CORS allowlist configured for staging/prod origins", "CORS gate"),
    ("CSP, HSTS and browser hardening headers enabled", "browser security header gate"),
    ("Browser contracts checked for platform token exposure", "browser token exposure gate"),
    ("Audit coverage review for sensitive Foundation actions", "audit coverage gate"),
    ("Periodic platform connection reconciliation worker", "connection reconciliation gate"),
    ("Idempotency keys for retry-safe lifecycle actions", "idempotency gate"),
    (
        "Discord/Twitch ownership verification before registration",
        "connection ownership verification gate",
    ),
    (
        "Discord/Twitch browser-safe connection health adapters",
        "connection health adapter gate",
    ),
    ("Privacy policy reviewed and published", "privacy policy launch gate"),
    ("Terms reviewed and published", "terms launch gate"),
    ("Data inventory and retention schedule approved", "data inventory launch gate"),
    ("Incident runbook approved and exercised", "incident runbook launch gate"),
    ("Backup/restore drill completed", "backup/restore launch gate"),
    ("Staging/prod domains provisioned", "domain provisioning gate"),
    ("Staging/prod OAuth credentials provisioned", "OAuth credential gate"),
    ("KMS/secret manager selected and wired", "secret manager gate"),
)

REQUIRED_SCOPE_MARKERS: tuple[tuple[str, str], ...] = (
    (
        "Email verification is intentionally out of scope for this Console Foundation",
        "email verification scope exclusion",
    ),
)

REQUIRED_BACKUP_DRILL_MARKERS: tuple[tuple[str, str], ...] = (
    ("Create encrypted database backup from staging", "encrypted staging backup step"),
    ("Restore into isolated environment", "isolated restore step"),
    ("Run migrations forward", "forward migration step"),
    ("Run one rollback migration test for the newest migration", "rollback migration step"),
    (
        "Verify account login, organization list, member list, platform connection",
        "product restore verification",
    ),
    ("does not restore revoked active sessions as", "revoked-session restore safety check"),
    (
        "Record restore time objective, data loss window and any manual steps",
        "RTO/RPO evidence step",
    ),
)

REQUIRED_CI_MARKERS: tuple[tuple[str, str], ...] = (
    ("python scripts/secret_scan.py", "secret scan command"),
    ("python scripts/browser_token_exposure_scan.py", "browser token exposure scan command"),
    ("python scripts/audit_coverage.py", "audit coverage command"),
    ("python scripts/production_composition_smoke.py", "production composition smoke command"),
    ("python scripts/readiness_artifact_check.py", "readiness artifact command"),
    ("python -m pytest", "backend test command"),
    ("npm test", "frontend unit test command"),
    ("npm run test:e2e", "frontend E2E command"),
    ("npm run build", "frontend production build command"),
    ("python -m alembic downgrade base", "migration rollback command"),
    ("docker compose -f docker-compose.dev.yml config", "development compose smoke command"),
)


def check_readiness_artifacts(root: Path = Path(".")) -> tuple[ReadinessArtifactIssue, ...]:
    readiness_path = root / "docs" / "operations" / "production-readiness.md"
    workflow_path = root / ".github" / "workflows" / "console-quality.yml"
    alerts_path = root / "docs" / "operations" / "prometheus-alerts.yml"

    issues: list[ReadinessArtifactIssue] = []
    readiness = _read_required_text(readiness_path, issues)
    workflow = _read_required_text(workflow_path, issues)
    alerts = _read_required_text(alerts_path, issues)

    _require_markers(readiness_path, readiness, REQUIRED_READINESS_MARKERS, issues)
    _require_markers(readiness_path, readiness, REQUIRED_LAUNCH_GATES, issues)
    _require_markers(readiness_path, readiness, REQUIRED_SCOPE_MARKERS, issues)
    _require_markers(readiness_path, readiness, REQUIRED_BACKUP_DRILL_MARKERS, issues)
    _require_markers(workflow_path, workflow, REQUIRED_CI_MARKERS, issues)
    _require_markers(
        alerts_path,
        alerts,
        (
            ("MuxivoConsoleHigh5xxRate", "5xx alert"),
            ("MuxivoConsoleHighAuthFailureRate", "auth failure/rate-limit alert"),
            ("MuxivoConsoleHighP95Latency", "latency alert"),
            ("MuxivoConsoleConnectionLifecycleFailures", "connection lifecycle alert"),
            ("MuxivoConsoleMetricsScrapeMissing", "metrics scrape alert"),
        ),
        issues,
    )
    return tuple(issues)


def _read_required_text(path: Path, issues: list[ReadinessArtifactIssue]) -> str:
    if not path.exists():
        issues.append(
            ReadinessArtifactIssue(
                artifact=path,
                marker=str(path),
                reason="required readiness artifact is missing",
            )
        )
        return ""
    return path.read_text(encoding="utf-8")


def _require_markers(
    artifact: Path,
    text: str,
    markers: tuple[tuple[str, str], ...],
    issues: list[ReadinessArtifactIssue],
) -> None:
    for marker, reason in markers:
        if marker not in text:
            issues.append(
                ReadinessArtifactIssue(
                    artifact=artifact,
                    marker=marker,
                    reason=f"missing {reason}",
                )
            )


def main() -> int:
    issues = check_readiness_artifacts()
    if not issues:
        print("Readiness artifact check passed.")
        return 0

    print("Readiness artifact check failed:")
    for issue in issues:
        print(f"- {issue.artifact}: {issue.reason}: {issue.marker!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
