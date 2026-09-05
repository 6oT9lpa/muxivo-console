"""Persist the reason for the current platform connection state.

Revision ID: 20260905_0007
Revises: 20260902_0006
Create Date: 2026-09-05 04:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260905_0007"
down_revision = "20260902_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_connections",
        sa.Column("status_reason", sa.String(64), nullable=True),
    )
    op.add_column(
        "platform_connection_lifecycle_idempotency",
        sa.Column("result_reason", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_connection_lifecycle_idempotency", "result_reason")
    op.drop_column("platform_connections", "status_reason")
