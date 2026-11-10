"""The Accounts Identity has registered, and the outbox that announces each one."""

import sqlalchemy as sa
from alembic import op

from kart.shared.outbox import create_outbox_table

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.Uuid, primary_key=True),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=False),
    )
    create_outbox_table()


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("accounts")
