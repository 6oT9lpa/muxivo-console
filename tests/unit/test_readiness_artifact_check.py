from pathlib import Path

from scripts.readiness_artifact_check import check_readiness_artifacts


def test_readiness_artifact_check_passes_current_artifacts() -> None:
    assert check_readiness_artifacts() == ()


def test_readiness_artifact_check_flags_removed_required_readiness_section(
    tmp_path: Path,
) -> None:
    _copy_required_artifacts(tmp_path)
    readiness_path = tmp_path / "docs" / "operations" / "production-readiness.md"
    readiness = readiness_path.read_text(encoding="utf-8")
    readiness_path.write_text(
        readiness.replace("## Backup/restore drill", "## Backup notes"),
        encoding="utf-8",
    )

    issues = check_readiness_artifacts(tmp_path)

    assert any(issue.marker == "## Backup/restore drill" for issue in issues)


def test_readiness_artifact_check_flags_removed_ci_gate(tmp_path: Path) -> None:
    _copy_required_artifacts(tmp_path)
    workflow_path = tmp_path / ".github" / "workflows" / "console-quality.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        workflow.replace("python scripts/audit_coverage.py", "python -m pytest"),
        encoding="utf-8",
    )

    issues = check_readiness_artifacts(tmp_path)

    assert any(issue.marker == "python scripts/audit_coverage.py" for issue in issues)


def test_readiness_artifact_check_flags_missing_supporting_operations_artifact(
    tmp_path: Path,
) -> None:
    _copy_required_artifacts(tmp_path)
    artifact = tmp_path / "docs" / "operations" / "incident-runbook.md"
    artifact.unlink()

    issues = check_readiness_artifacts(tmp_path)

    assert any(issue.artifact == artifact for issue in issues)


def test_readiness_artifact_check_flags_missing_secret_manager_artifact(
    tmp_path: Path,
) -> None:
    _copy_required_artifacts(tmp_path)
    artifact = tmp_path / "deploy" / "vault-policy.hcl.example"
    artifact.unlink()

    issues = check_readiness_artifacts(tmp_path)

    assert any(issue.artifact == artifact for issue in issues)


def test_readiness_artifact_check_keeps_email_verification_in_authentication_scope(
    tmp_path: Path,
) -> None:
    _copy_required_artifacts(tmp_path)
    readiness_path = tmp_path / "docs" / "operations" / "production-readiness.md"
    readiness = readiness_path.read_text(encoding="utf-8")
    readiness_path.write_text(
        readiness.replace(
            "E-mail ownership verification is part of the current Console authentication",
            "E-mail ownership verification was removed from Console authentication",
        ),
        encoding="utf-8",
    )

    issues = check_readiness_artifacts(tmp_path)

    assert any(
        issue.marker
        == "E-mail ownership verification is part of the current Console authentication"
        for issue in issues
    )


def _copy_required_artifacts(destination: Path) -> None:
    for source in (
        Path("docs/operations/production-readiness.md"),
        Path("docs/operations/prometheus-alerts.yml"),
        Path("docs/legal/privacy-policy.draft.md"),
        Path("docs/legal/terms-of-service.draft.md"),
        Path("docs/operations/data-inventory.md"),
        Path("docs/operations/retention-policy.md"),
        Path("docs/operations/incident-runbook.md"),
        Path("deploy/prometheus-console.yml.example"),
        Path("deploy/vault-agent.hcl.example"),
        Path("deploy/console.env.ctmpl.example"),
        Path("deploy/vault-policy.hcl.example"),
        Path("deploy/muxivo-console-vault-agent.service"),
        Path("deploy/muxivo-console-api.service"),
        Path(".github/workflows/console-quality.yml"),
    ):
        target = destination / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
