"""Fail quality gates when removed legacy registration artifacts reappear."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

_IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    ".nox",
    ".tox",
    "build",
    "dist",
    "node_modules",
    "venv",
}
_IGNORED_SUFFIXES = {
    ".docx",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".pyc",
    ".sqlite",
    ".db",
}
_LEGACY_AUTH_PATTERN = re.compile(
    r"(?i)\b(?:direct[-_\s]+registration|register_email_password|"
    r"account_accepted|auto-created\s+demo|muxivo-demo-password|demo@example)\b"
)
_LEGACY_FILE_NAME_PATTERN = re.compile(r"(?i)(?:register_email_password|direct[-_]registration)")
_SELF_SCAN_FILES = {
    Path("scripts/legacy_auth_scan.py"),
    Path("tests/unit/test_legacy_auth_scan.py"),
}


@dataclass(frozen=True, slots=True)
class LegacyAuthFinding:
    """Describe one legacy artifact without exposing file contents in CI output."""

    path: Path
    line_number: int | None
    kind: str


def scan_repository(root: Path) -> list[LegacyAuthFinding]:
    """Scan source, tests and operational artifacts for removed auth flows."""

    findings: list[LegacyAuthFinding] = []
    for path in _iter_candidate_files(root):
        relative_path = path.relative_to(root)
        if relative_path in _SELF_SCAN_FILES:
            continue
        if _LEGACY_FILE_NAME_PATTERN.search(path.name):
            findings.append(LegacyAuthFinding(path=path, line_number=None, kind="file_name"))
        for line_number, line in enumerate(_read_text_lines(path), start=1):
            if _LEGACY_AUTH_PATTERN.search(line):
                findings.append(LegacyAuthFinding(path=path, line_number=line_number, kind="text"))
    return findings


def _iter_candidate_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if any(part in _IGNORED_DIRECTORIES for part in relative_path.parts):
            continue
        if path.suffix.lower() in _IGNORED_SUFFIXES:
            continue
        if relative_path in _SELF_SCAN_FILES:
            continue
        yield path


def _read_text_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan_repository(root)
    if not findings:
        print("Legacy auth scan passed: no removed registration artifacts found.")
        return 0

    print("Legacy auth scan failed:")
    for finding in findings:
        relative_path = finding.path.resolve().relative_to(root)
        location = str(relative_path)
        if finding.line_number is not None:
            location = f"{location}:{finding.line_number}"
        print(f"- {location} ({finding.kind})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
