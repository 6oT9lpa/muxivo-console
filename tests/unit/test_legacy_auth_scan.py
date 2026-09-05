from pathlib import Path

from scripts.legacy_auth_scan import scan_repository


def test_legacy_auth_scan_rejects_removed_registration_file_and_text(tmp_path: Path) -> None:
    legacy_flow_name = "_".join(("register", "email", "password"))
    legacy_file = tmp_path / "apps" / "api" / f"{legacy_flow_name}.py"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text(f"def {legacy_flow_name}(): pass\n", encoding="utf-8")

    findings = scan_repository(tmp_path)

    assert len(findings) == 2
    assert {finding.kind for finding in findings} == {"file_name", "text"}


def test_legacy_auth_scan_allows_current_registration_flow(tmp_path: Path) -> None:
    current_file = tmp_path / "apps" / "api" / "start_email_password_registration.py"
    current_file.parent.mkdir(parents=True)
    current_file.write_text(
        "def start_email_password_registration(): pass\n",
        encoding="utf-8",
    )

    assert scan_repository(tmp_path) == []
