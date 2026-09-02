"""Persist the delivery result of organization invitations.

Revision ID: 20260902_0006
Revises: 20260902_0005
Create Date: 2026-09-02 13:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_0006"
down_revision = "20260902_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_invitations",
        sa.Column("delivery_status", sa.String(16), nullable=True),
    )
    op.create_check_constraint(
        "ck_organization_invitations_delivery_status",
        "organization_invitations",
        "delivery_status IS NULL OR delivery_status IN ('sent', 'unavailable', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_organization_invitations_delivery_status",
        "organization_invitations",
        type_="check",
    )
    op.drop_column("organization_invitations", "delivery_status")
