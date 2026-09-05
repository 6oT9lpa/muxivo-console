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
    (
        (
            "E-mail/password registration creates an account only after a short-lived "
            "six-digit code is verified"
        ),
        "e-mail ownership verification gate",
    ),
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
        "E-mail ownership verification is part of the current Console authentication",
        "e-mail ownership verification scope",
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

REQUIRED_SUPPORTING_ARTIFACTS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "docs/legal/privacy-policy.draft.md",
        (
            ("# Muxivo Console Privacy Policy — Draft", "privacy policy draft title"),
            ("must not be published until", "privacy publication review warning"),
        ),
    ),
    (
        "docs/legal/terms-of-service.draft.md",
        (("# Muxivo Console Terms of Service — Draft", "terms draft title"),),
    ),
    (
        "docs/operations/data-inventory.md",
        (("# Muxivo Console Data Inventory — Draft", "data inventory title"),),
    ),
    (
        "docs/operations/retention-policy.md",
        (("# Muxivo Console Retention Policy — Draft", "retention policy title"),),
    ),
    (
        "docs/operations/incident-runbook.md",
        (("# Muxivo Console Incident Runbook — Draft", "incident runbook title"),),
    ),
    (
        "deploy/prometheus-console.yml.example",
        (
            ("scrape_configs:", "Prometheus scrape configuration"),
            ("job_name: muxivo-console", "Console scrape job"),
            ("127.0.0.1:8010", "loopback API target"),
            ("127.0.0.1:9093", "private Alertmanager target"),
        ),
    ),
    (
        "deploy/alertmanager-console.dev.yml.example",
        (
            ("route:", "Alertmanager route"),
            ("receiver: dev-null", "safe development receiver"),
        ),
    ),
    (
        "deploy/vault-agent.hcl.example",
        (
            ("auto_auth", "Vault Agent auto-authentication"),
            ("auth/approle", "Vault AppRole authentication mount"),
            ("console.env.ctmpl", "Vault-rendered Console environment template"),
        ),
    ),
    (
        "deploy/vault-server.hcl.example",
        (
            ('storage "raft"', "persistent staging Vault storage"),
            ('address         = "127.0.0.1:8200"', "loopback Vault listener"),
            ('tls_min_version = "tls13"', "TLS 1.3 Vault listener"),
        ),
    ),
    (
        "deploy/vault-server.service",
        (
            ("User=vault", "dedicated Vault service user"),
            (
                "ReadWritePaths=/var/lib/vault /var/log/vault",
                "isolated Vault data and audit paths",
            ),
            ("ExecStart=/usr/local/bin/vault server", "Vault server process"),
        ),
    ),
    (
        "deploy/console.env.ctmpl.example",
        (
            ('secret "secret/data/muxivo-console/staging"', "staging Vault KV path"),
            ("MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY", "encrypted e-mail key mapping"),
            ("MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER", "session pepper mapping"),
            ("MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD", "SMTP password mapping"),
        ),
    ),
    (
        "deploy/console.env.production.ctmpl.example",
        (
            (
                'secret "secret/data/muxivo-console/production"',
                "production Vault KV path",
            ),
            (
                "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY",
                "encrypted e-mail key mapping",
            ),
            (
                "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER",
                "session pepper mapping",
            ),
            (
                "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD",
                "SMTP password mapping",
            ),
        ),
    ),
    (
        "deploy/vault-policy.hcl.example",
        (
            ('path "secret/data/muxivo-console/staging"', "staging Vault policy path"),
            ('capabilities = ["read"]', "read-only Vault policy"),
        ),
    ),
    (
        "deploy/vault-policy.production.hcl.example",
        (
            (
                'path "secret/data/muxivo-console/production"',
                "production Vault policy path",
            ),
            ('capabilities = ["read"]', "read-only Vault policy"),
        ),
    ),
    (
        "deploy/muxivo-console-vault-agent.service",
        (
            ("ExecStart=/usr/local/bin/vault agent", "Vault Agent service command"),
            ("RuntimeDirectory=muxivo-console-vault-agent", "isolated Vault Agent runtime"),
            ("Environment=HOME=/run/muxivo-console-vault-agent", "Vault Agent runtime home"),
        ),
    ),
    (
        "deploy/muxivo-discord-vault-agent.service",
        (
            ("ExecStart=/usr/local/bin/vault agent", "Discord Vault Agent service command"),
            ("RuntimeDirectory=muxivo-discord-vault-agent", "isolated Discord Agent runtime"),
            ("Environment=HOME=/run/muxivo-discord-vault-agent", "Discord Agent runtime home"),
        ),
    ),
    (
        "deploy/discord-vault-agent.hcl.example",
        (
            ("auth/approle", "Discord AppRole authentication mount"),
            ("discord-control.env.ctmpl", "Discord Control environment template"),
        ),
    ),
    (
        "deploy/discord-control.env.ctmpl.example",
        (
            ("MUXIVO_DISCORD_CONTROL_SIGNING_KEY", "Discord Control signing key mapping"),
            ("secret/data/muxivo-discord/staging", "Discord Control KV path"),
        ),
    ),
    (
        "deploy/vault-policy.discord.hcl.example",
        (
            ('path "secret/data/muxivo-discord/staging"', "Discord read-only Vault policy path"),
            ('capabilities = ["read"]', "Discord read-only Vault policy"),
        ),
    ),
    (
        "deploy/muxivo-discord-activity-vault.conf.example",
        (
            ("Requires=muxivo-discord-vault-agent.service", "Activity-to-Discord-Agent dependency"),
            (
                "EnvironmentFile=/run/muxivo-discord-vault-agent/control.env",
                "Discord Control runtime credential source",
            ),
        ),
    ),
    (
        "deploy/muxivo-console-api.service",
        (
            (
                "Requires=muxivo-console-vault-agent.service",
                "API-to-Vault-Agent dependency",
            ),
            (
                "LoadCredential=console_env:/run/muxivo-console-vault-agent/console.env",
                "API runtime credential source",
            ),
        ),
    ),
)

REQUIRED_CI_MARKERS: tuple[tuple[str, str], ...] = (
    ("python scripts/secret_scan.py", "secret scan command"),
    ("python scripts/legacy_auth_scan.py", "legacy auth scan command"),
    ("python scripts/browser_token_exposure_scan.py", "browser token exposure scan command"),
    ("python scripts/audit_coverage.py", "audit coverage command"),
    ("python scripts/production_composition_smoke.py", "production composition smoke command"),
    ("python scripts/readiness_artifact_check.py", "readiness artifact command"),
    ("python -m pytest", "backend test command"),
    ("npm test", "frontend unit test command"),
    ("npm run test:e2e", "frontend E2E command"),
    ("npm run build", "frontend production build command"),
    ("python -m alembic downgrade base", "migration rollback command"),
    (
        "python scripts/development_composition_smoke.py",
        "development compose runtime smoke command",
    ),
    (
        "python scripts/observability_composition_smoke.py",
        "development observability compose runtime smoke command",
    ),
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
    for relative_path, markers in REQUIRED_SUPPORTING_ARTIFACTS:
        artifact_path = root / relative_path
        artifact_text = _read_required_text(artifact_path, issues)
        _require_markers(artifact_path, artifact_text, markers, issues)
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
