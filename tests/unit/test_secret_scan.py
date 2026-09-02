"""Tests for repository secret-scan boundaries."""

from pathlib import Path

from scripts.secret_scan import scan_repository


def test_secret_scan_ignores_virtual_environment_artifacts(tmp_path: Path) -> None:
    virtualenv_file = tmp_path / "venv" / "lib" / "python3.12" / "site.py"
    virtualenv_file.parent.mkdir(parents=True)
    virtualenv_file.write_text(
        "-----" + "BEGIN OPENSSH PRIVATE KEY" + "-----\n",
        encoding="utf-8",
    )

    assert scan_repository(tmp_path) == []


def test_secret_scan_still_reports_source_private_key_material(tmp_path: Path) -> None:
    source_file = tmp_path / "settings.py"
    source_file.write_text(
        "signing_" + "key = " + '"' + ("a" * 32) + '"\n',
        encoding="utf-8",
    )

    findings = scan_repository(tmp_path)

    assert [(finding.path, finding.kind) for finding in findings] == [(source_file, "signing_key")]
