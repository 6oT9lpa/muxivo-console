"""Tests for the application class-layout quality gate."""

from pathlib import Path

from scripts.application_class_layout_check import (
    check_application_class_layout,
    check_settings_class_layout,
)


def _application_root(root: Path) -> Path:
    application_root = root / "apps" / "api" / "src" / "muxivo_console" / "application"
    application_root.mkdir(parents=True)
    return application_root


def test_class_layout_check_allows_single_class_modules_and_ports_registry(
    tmp_path: Path,
) -> None:
    application_root = _application_root(tmp_path)
    (application_root / "single.py").write_text("class Single:\n    pass\n", encoding="utf-8")
    (application_root / "ports.py").write_text(
        "class First:\n    pass\nclass Second:\n    pass\n",
        encoding="utf-8",
    )

    assert check_application_class_layout(tmp_path) == ()


def test_class_layout_check_reports_multiple_concrete_classes(tmp_path: Path) -> None:
    application_root = _application_root(tmp_path)
    (application_root / "invalid.py").write_text(
        "class First:\n    pass\nclass Second:\n    pass\n",
        encoding="utf-8",
    )

    issues = check_application_class_layout(tmp_path)

    assert len(issues) == 1
    assert issues[0].path == application_root / "invalid.py"
    assert issues[0].classes == ("First", "Second")


def test_settings_class_layout_check_allows_the_configuration_facade() -> None:
    assert check_settings_class_layout() == ()


def test_settings_class_layout_check_reports_multiple_configuration_classes(
    tmp_path: Path,
) -> None:
    settings_path = (
        tmp_path / "apps" / "api" / "src" / "muxivo_console" / "infrastructure" / "settings.py"
    )
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        "class First:\n    pass\nclass Second:\n    pass\n",
        encoding="utf-8",
    )

    issues = check_settings_class_layout(tmp_path)

    assert len(issues) == 1
    assert issues[0].path == settings_path
    assert issues[0].classes == ("First", "Second")
