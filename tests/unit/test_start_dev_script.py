from pathlib import Path


def test_development_launcher_does_not_create_a_bypass_account() -> None:
    script = Path("scripts/start-dev.ps1").read_text(encoding="utf-8")

    assert "$demoPayload" not in script
    assert "ConvertTo-Json" not in script
    assert "Demo sign-in:" not in script
    assert "six-digit e-mail code" in script
