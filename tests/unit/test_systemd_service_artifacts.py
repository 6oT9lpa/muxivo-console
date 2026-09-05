from pathlib import Path


SERVICE_PATH = Path("deploy/muxivo-console-api.service")


def test_console_api_service_keeps_runtime_condition_in_unit_section() -> None:
    service = SERVICE_PATH.read_text(encoding="utf-8")

    unit_section, service_section = service.split("[Service]", maxsplit=1)

    assert "ConditionPathExists=/run/muxivo-console-vault-agent/console.env" in unit_section
    assert "ConditionPathExists=/run/muxivo-console-vault-agent/console.env" not in service_section


def test_console_api_service_loads_only_vault_agent_runtime_credentials() -> None:
    service = SERVICE_PATH.read_text(encoding="utf-8")

    assert "LoadCredential=console_env:/run/muxivo-console-vault-agent/console.env" in service
    assert "EnvironmentFile=%d/console_env" in service
    assert "MUXIVO_CONSOLE_PASSWORD_RECOVERY_SMTP_PASSWORD" not in service
