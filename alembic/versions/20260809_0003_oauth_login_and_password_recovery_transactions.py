"""Create OAuth login and password recovery transaction storage.

Revision ID: 20260809_0003
Revises: 20260809_0002
Create Date: 2026-08-09 02:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260809_0003"
down_revision = "20260809_0002"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "oauth_login_transactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_verifier_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("consumed_at", TIMESTAMP),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "provider IN ('discord', 'twitch', 'google', 'yandex')",
            name="ck_oauth_login_transactions_provider",
        ),
    )
    op.create_index(
        "ix_oauth_login_transactions_state_expires",
        "oauth_login_transactions",
        ["state_hash", "expires_at"],
    )
    op.create_table(
        "password_recovery_transactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("consumed_at", TIMESTAMP),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_password_recovery_transactions_token_expires",
        "password_recovery_transactions",
        ["token_hash", "expires_at"],
    )
    op.create_index(
        "ix_password_recovery_transactions_user_id",
        "password_recovery_transactions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_recovery_transactions_user_id",
        table_name="password_recovery_transactions",
    )
    op.drop_index(
        "ix_password_recovery_transactions_token_expires",
        table_name="password_recovery_transactions",
    )
    op.drop_table("password_recovery_transactions")
    op.drop_index(
        "ix_oauth_login_transactions_state_expires",
        table_name="oauth_login_transactions",
    )
    op.drop_table("oauth_login_transactions")
