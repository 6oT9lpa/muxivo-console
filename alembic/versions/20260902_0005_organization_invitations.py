"""Add one-time organization membership invitations.

Revision ID: 20260902_0005
Revises: 20260809_0004
Create Date: 2026-09-02 12:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260902_0005"
down_revision = "20260809_0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMP = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("email_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("email_lookup_hash", sa.String(64), nullable=False),
        sa.Column("email_hint", sa.String(192), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("accepted_at", TIMESTAMP),
        sa.Column("revoked_at", TIMESTAMP),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "role IN ('admin', 'moderator', 'analyst', 'viewer')",
            name="ck_organization_invitations_role",
        ),
    )
    op.create_index(
        "ix_organization_invitations_organization_created",
        "organization_invitations",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_organization_invitations_email_lookup_hash",
        "organization_invitations",
        ["email_lookup_hash"],
    )
    op.create_index(
        "ix_organization_invitations_token_expires",
        "organization_invitations",
        ["token_hash", "expires_at"],
    )
    op.create_table(
        "organization_invitation_scopes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "invitation_id",
            UUID,
            sa.ForeignKey("organization_invitations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource", sa.String(96), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "invitation_id",
            "resource",
            "action",
            name="uq_organization_invitation_scope",
        ),
    )
    op.create_index(
        "ix_organization_invitation_scopes_invitation_id",
        "organization_invitation_scopes",
        ["invitation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_invitation_scopes_invitation_id",
        table_name="organization_invitation_scopes",
    )
    op.drop_table("organization_invitation_scopes")
    op.drop_index(
        "ix_organization_invitations_token_expires",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_email_lookup_hash",
        table_name="organization_invitations",
    )
    op.drop_index(
        "ix_organization_invitations_organization_created",
        table_name="organization_invitations",
    )
    op.drop_table("organization_invitations")
