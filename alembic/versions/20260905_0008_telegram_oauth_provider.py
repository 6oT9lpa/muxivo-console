"""Allow Telegram Login OIDC transactions."""

import sqlalchemy as sa

from alembic import op

revision = "20260905_0008"
down_revision = "20260905_0007"
branch_labels = None
depends_on = None

_PROVIDERS_WITH_TELEGRAM = "provider IN ('discord', 'twitch', 'telegram', 'google', 'yandex')"
_PROVIDERS_WITHOUT_TELEGRAM = "provider IN ('discord', 'twitch', 'google', 'yandex')"


def upgrade() -> None:
    for table_name, constraint_name in (
        ("identity_link_transactions", "ck_identity_link_transactions_provider"),
        ("oauth_login_transactions", "ck_oauth_login_transactions_provider"),
    ):
        op.drop_constraint(constraint_name, table_name=table_name, type_="check")
        op.create_check_constraint(
            constraint_name,
            table_name,
            sa.text(_PROVIDERS_WITH_TELEGRAM),
        )


def downgrade() -> None:
    for table_name, constraint_name in (
        ("oauth_login_transactions", "ck_oauth_login_transactions_provider"),
        ("identity_link_transactions", "ck_identity_link_transactions_provider"),
    ):
        op.drop_constraint(constraint_name, table_name=table_name, type_="check")
        op.create_check_constraint(
            constraint_name,
            table_name,
            sa.text(_PROVIDERS_WITHOUT_TELEGRAM),
        )
