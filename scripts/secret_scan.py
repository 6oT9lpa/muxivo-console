"""Fail CI when obviously hardcoded production secrets enter the repository."""

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
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pyc",
    ".sqlite",
    ".db",
}
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(access_token|refresh_token|client_secret|bot_token|activity_token|"
    r"session_token|recovery_token|oauth_token|signing_key|encryption_key|lookup_key|"
    r"token_pepper|pepper|fernet_key)\b\s*[:=]\s*([\"']?)"
    r"([A-Za-z0-9._~+/=-]{24,})(?:\2|[\s,}#])"
)
_DISCORD_BOT_TOKEN_PATTERN = re.compile(
    r"\b(?:mfa\.)?[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b"
)
_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_SAFE_VALUES = {
    "[redacted]",
    "changeme",
    "example",
    "placeholder",
}


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: Path
    line_number: int
    kind: str


def scan_repository(root: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in _iter_candidate_files(root):
        for line_number, line in enumerate(_read_text_lines(path), start=1):
            findings.extend(_scan_line(path, line_number, line))
    return findings


def _iter_candidate_files(root: Path):
    scanner_path = Path(__file__).resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == scanner_path:
            continue
        if any(part in _IGNORED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() in _IGNORED_SUFFIXES:
            continue
        yield path


def _read_text_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []


def _scan_line(path: Path, line_number: int, line: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for match in _ASSIGNMENT_PATTERN.finditer(line):
        value = match.group(3).strip().lower()
        if value not in _SAFE_VALUES and not _looks_like_runtime_reference(value):
            findings.append(SecretFinding(path=path, line_number=line_number, kind=match.group(1)))
    if _DISCORD_BOT_TOKEN_PATTERN.search(line):
        findings.append(SecretFinding(path=path, line_number=line_number, kind="discord_bot_token"))
    if _PRIVATE_KEY_PATTERN.search(line):
        findings.append(SecretFinding(path=path, line_number=line_number, kind="private_key"))
    return findings


def _looks_like_runtime_reference(value: str) -> bool:
    return value.startswith(
        (
            "settings.",
            "self.",
            "config.",
            "environment.",
            "os.environ",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan_repository(root)
    if not findings:
        print("Secret scan passed: no obvious hardcoded secrets found.")
        return 0
    print("Secret scan failed:")
    for finding in findings:
        relative_path = finding.path.resolve().relative_to(root)
        print(f"- {relative_path}:{finding.line_number} suspicious {finding.kind}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
