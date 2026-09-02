"""Enforce one concrete top-level class per selected production module."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

APPLICATION_RELATIVE_PATH = Path("apps/api/src/muxivo_console/application")
SETTINGS_RELATIVE_PATH = Path("apps/api/src/muxivo_console/infrastructure/settings.py")
SECURITY_RELATIVE_PATH = Path("apps/api/src/muxivo_console/infrastructure/security.py")
INTENTIONAL_REGISTRY_FILES = frozenset({"ports.py"})


@dataclass(frozen=True, slots=True)
class ClassLayoutIssue:
    """Describe an application module that violates the class layout rule."""

    path: Path
    classes: tuple[str, ...]


def check_application_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return modules with more than one concrete top-level class definition."""

    application_root = root / APPLICATION_RELATIVE_PATH
    issues: list[ClassLayoutIssue] = []
    for path in sorted(application_root.glob("*.py")):
        if path.name in INTENTIONAL_REGISTRY_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = tuple(node.name for node in tree.body if isinstance(node, ast.ClassDef))
        if len(classes) > 1:
            issues.append(ClassLayoutIssue(path=path, classes=classes))
    return tuple(issues)


def check_settings_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return configuration modules that define more than one class."""
    settings_path = root / SETTINGS_RELATIVE_PATH
    if not settings_path.exists():
        return ()
    tree = ast.parse(settings_path.read_text(encoding="utf-8"), filename=str(settings_path))
    classes = tuple(node.name for node in tree.body if isinstance(node, ast.ClassDef))
    if len(classes) <= 1:
        return ()
    return (ClassLayoutIssue(path=settings_path, classes=classes),)


def check_security_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return the security adapter facade if it defines multiple classes."""
    security_path = root / SECURITY_RELATIVE_PATH
    if not security_path.exists():
        return ()
    tree = ast.parse(security_path.read_text(encoding="utf-8"), filename=str(security_path))
    classes = tuple(node.name for node in tree.body if isinstance(node, ast.ClassDef))
    if len(classes) <= 1:
        return ()
    return (ClassLayoutIssue(path=security_path, classes=classes),)


def main() -> int:
    """Run the check and print actionable violations for local and CI users."""

    issues = (
        check_application_class_layout()
        + check_settings_class_layout()
        + check_security_class_layout()
    )
    if issues:
        for issue in issues:
            print(f"{issue.path}: {', '.join(issue.classes)}")
        return 1
    print("Application, settings and security class layout check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
