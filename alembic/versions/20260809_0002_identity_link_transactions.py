"""Create single-use external identity link transaction storage.

Revision ID: 20260809_0002
Revises: 20260809_0001
Create Date: 2026-08-09 01:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260809_0002"
down_revision = "20260809_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_link_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_verifier_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumed_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "provider IN ('discord', 'twitch', 'google', 'yandex')",
            name="ck_identity_link_transactions_provider",
        ),
    )
    op.create_index(
        "ix_identity_link_transactions_state_expires",
        "identity_link_transactions",
        ["state_hash", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_link_transactions_state_expires", table_name="identity_link_transactions"
    )
    op.drop_table("identity_link_transactions")
