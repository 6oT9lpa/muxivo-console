"""Persist platform connection lifecycle idempotency results.

Revision ID: 20260809_0004
Revises: 20260809_0003
Create Date: 2026-08-09 03:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260809_0004"
down_revision = "20260809_0003"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "platform_connection_lifecycle_idempotency",
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column(
            "connection_id",
            UUID,
            sa.ForeignKey("platform_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("result_status", sa.String(32), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "action IN ('reauthorize', 'revoke', 'disconnect')",
            name="ck_platform_connection_lifecycle_idempotency_action",
        ),
        sa.CheckConstraint(
            "result_status IN ('pending', 'active', 'degraded', "
            "'reauth_required', 'disconnected')",
            name="ck_platform_connection_lifecycle_idempotency_result_status",
        ),
    )
    op.create_index(
        "ix_platform_connection_lifecycle_idempotency_connection_id",
        "platform_connection_lifecycle_idempotency",
        ["connection_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_connection_lifecycle_idempotency_connection_id",
        table_name="platform_connection_lifecycle_idempotency",
    )
    op.drop_table("platform_connection_lifecycle_idempotency")
