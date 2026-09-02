"""Enforce one concrete top-level class per selected production module."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

APPLICATION_RELATIVE_PATH = Path("apps/api/src/muxivo_console/application")
SETTINGS_RELATIVE_PATH = Path("apps/api/src/muxivo_console/infrastructure/settings.py")
SECURITY_RELATIVE_PATH = Path("apps/api/src/muxivo_console/infrastructure/security.py")
RATE_LIMITING_RELATIVE_PATH = Path("apps/api/src/muxivo_console/infrastructure/rate_limiting.py")
WORKER_FACADE_RELATIVE_PATHS = (
    Path("apps/api/src/muxivo_console/infrastructure/reconciliation_worker.py"),
    Path("apps/api/src/muxivo_console/infrastructure/security_cleanup_worker.py"),
)
ADDITIONAL_FACADE_RELATIVE_PATHS = (
    Path("apps/api/src/muxivo_console/infrastructure/development.py"),
    Path("apps/api/src/muxivo_console/infrastructure/metrics.py"),
    Path("apps/api/src/muxivo_console/presentation/api.py"),
)
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
    return _check_single_module(root, SETTINGS_RELATIVE_PATH)


def check_security_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return the security adapter facade if it defines multiple classes."""
    return _check_single_module(root, SECURITY_RELATIVE_PATH)


def check_rate_limiting_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return the rate-limit adapter facade if it defines multiple classes."""
    return _check_single_module(root, RATE_LIMITING_RELATIVE_PATH)


def check_worker_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return runtime worker facades that define more than one class."""
    issues: list[ClassLayoutIssue] = []
    for relative_path in WORKER_FACADE_RELATIVE_PATHS:
        issues.extend(_check_single_module(root, relative_path))
    return tuple(issues)


def check_additional_facade_class_layout(root: Path = Path(".")) -> tuple[ClassLayoutIssue, ...]:
    """Return selected infrastructure/presentation facades with multiple classes."""
    issues: list[ClassLayoutIssue] = []
    for relative_path in ADDITIONAL_FACADE_RELATIVE_PATHS:
        issues.extend(_check_single_module(root, relative_path))
    return tuple(issues)


def _check_single_module(root: Path, relative_path: Path) -> tuple[ClassLayoutIssue, ...]:
    module_path = root / relative_path
    if not module_path.exists():
        return ()
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    classes = tuple(node.name for node in tree.body if isinstance(node, ast.ClassDef))
    if len(classes) <= 1:
        return ()
    return (ClassLayoutIssue(path=module_path, classes=classes),)


def main() -> int:
    """Run the check and print actionable violations for local and CI users."""

    issues = (
        check_application_class_layout()
        + check_settings_class_layout()
        + check_security_class_layout()
        + check_rate_limiting_class_layout()
        + check_worker_class_layout()
        + check_additional_facade_class_layout()
    )
    if issues:
        for issue in issues:
            print(f"{issue.path}: {', '.join(issue.classes)}")
        return 1
    print("Selected production class layout check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
