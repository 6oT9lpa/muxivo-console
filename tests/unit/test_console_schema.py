import importlib
import inspect
import pkgutil

import muxivo_console.contracts.v1 as contracts_v1
from muxivo_console.infrastructure.persistence import models  # noqa: F401
from muxivo_console.infrastructure.persistence.base import Base
from pydantic import BaseModel


def test_foundation_schema_owns_only_console_control_plane_records() -> None:
    expected_tables = {
        "users",
        "login_identities",
        "identity_link_transactions",
        "oauth_login_transactions",
        "user_emails",
        "password_credentials",
        "password_recovery_transactions",
        "organizations",
        "organization_memberships",
        "membership_resource_scopes",
        "auth_sessions",
        "platform_connections",
        "platform_connection_lifecycle_idempotency",
        "audit_events",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_console_schema_never_maps_platform_credentials_or_activity_tokens() -> None:
    forbidden_column_names = {
        "access_token",
        "refresh_token",
        "client_secret",
        "bot_token",
        "activity_token",
    }

    mapped_column_names = {
        column.name for table in Base.metadata.tables.values() for column in table.columns
    }

    assert forbidden_column_names.isdisjoint(mapped_column_names)


def test_browser_sessions_are_stored_as_hashes_only() -> None:
    session_columns = Base.metadata.tables["auth_sessions"].columns

    assert "token_hash" in session_columns
    assert "token" not in session_columns


def test_platform_connection_state_explanation_is_non_secret_metadata() -> None:
    connection_columns = Base.metadata.tables["platform_connections"].columns
    idempotency_columns = Base.metadata.tables["platform_connection_lifecycle_idempotency"].columns

    assert "status_reason" in connection_columns
    assert "result_reason" in idempotency_columns


def test_password_recovery_tokens_are_stored_as_hashes_only() -> None:
    recovery_columns = Base.metadata.tables["password_recovery_transactions"].columns

    assert "token_hash" in recovery_columns
    assert "token" not in recovery_columns


def test_browser_response_contracts_never_expose_platform_credentials() -> None:
    forbidden_field_names = {
        "access_token",
        "refresh_token",
        "client_secret",
        "bot_token",
        "activity_token",
        "platform_access_token",
        "platform_refresh_token",
    }

    leaked_fields: set[str] = set()
    for contract in _iter_browser_response_contracts():
        for field_name, field in contract.model_fields.items():
            exposed_name = field.alias or field_name
            if field_name in forbidden_field_names or exposed_name in forbidden_field_names:
                leaked_fields.add(f"{contract.__name__}.{exposed_name}")

    assert not leaked_fields


def _iter_browser_response_contracts() -> list[type[BaseModel]]:
    response_contracts: list[type[BaseModel]] = []
    for module_info in pkgutil.iter_modules(contracts_v1.__path__, f"{contracts_v1.__name__}."):
        module = importlib.import_module(module_info.name)
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(candidate, BaseModel)
                and candidate.__module__ == module.__name__
                and candidate.__name__.endswith(("Response", "ListResponse"))
            ):
                response_contracts.append(candidate)
    return response_contracts
