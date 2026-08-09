"""Create Console-owned identity, tenancy, session, connection and audit tables.

Revision ID: 20260809_0001
Revises:
Create Date: 2026-08-09 00:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260809_0001"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMP = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("last_authenticated_at", TIMESTAMP),
        sa.Column("deleted_at", TIMESTAMP),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending_verification', 'active', 'suspended', 'deleted')",
            name="ck_users_status",
        ),
    )
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(96), nullable=False, unique=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "login_identities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("linked_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", TIMESTAMP),
        sa.UniqueConstraint(
            "provider", "provider_subject", name="uq_login_identity_provider_subject"
        ),
    )
    op.create_index("ix_login_identities_user_id", "login_identities", ["user_id"])
    op.create_table(
        "user_emails",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("email_lookup_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("verified_at", TIMESTAMP),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_user_emails_user_id", "user_emails", ["user_id"])
    op.create_table(
        "password_credentials",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column(
            "password_changed_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", TIMESTAMP),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_membership"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'moderator', 'analyst', 'viewer')",
            name="ck_organization_memberships_role",
        ),
    )
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
    op.create_table(
        "membership_resource_scopes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "membership_id",
            UUID,
            sa.ForeignKey("organization_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource", sa.String(96), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(32)),
        sa.Column("external_resource_id", sa.String(255)),
        sa.Column("module_key", sa.String(128)),
    )
    op.create_index(
        "ix_membership_resource_scopes_membership_id",
        "membership_resource_scopes",
        ["membership_id"],
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("revoked_at", TIMESTAMP),
        sa.Column("assurance_level", sa.String(32), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("user_agent_hash", sa.String(64)),
        sa.Column("last_seen_at", TIMESTAMP),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "platform_connections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_resource_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "granted_capabilities", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("last_checked_at", TIMESTAMP),
        sa.Column("reauthorization_required_at", TIMESTAMP),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "platform", "external_resource_id", name="uq_platform_connection_external_resource"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'degraded', 'reauth_required', 'disconnected')",
            name="ck_platform_connections_status",
        ),
    )
    op.create_index(
        "ix_platform_connections_organization_id", "platform_connections", ["organization_id"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("actor_id", UUID),
        sa.Column("organization_id", UUID),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "result IN ('allowed', 'denied', 'succeeded', 'failed')", name="ck_audit_events_result"
        ),
    )
    op.create_index(
        "ix_audit_events_organization_created_at", "audit_events", ["organization_id", "created_at"]
    )
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_platform_connections_organization_id", table_name="platform_connections")
    op.drop_table("platform_connections")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        "ix_membership_resource_scopes_membership_id", table_name="membership_resource_scopes"
    )
    op.drop_table("membership_resource_scopes")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_table("password_credentials")
    op.drop_index("ix_user_emails_user_id", table_name="user_emails")
    op.drop_table("user_emails")
    op.drop_index("ix_login_identities_user_id", table_name="login_identities")
    op.drop_table("login_identities")
    op.drop_table("organizations")
    op.drop_table("users")
