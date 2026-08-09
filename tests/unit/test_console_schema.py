from muxivo_console.infrastructure.persistence import models  # noqa: F401
from muxivo_console.infrastructure.persistence.base import Base


def test_foundation_schema_owns_only_console_control_plane_records() -> None:
    expected_tables = {
        "users",
        "login_identities",
        "user_emails",
        "password_credentials",
        "organizations",
        "organization_memberships",
        "membership_resource_scopes",
        "auth_sessions",
        "platform_connections",
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
