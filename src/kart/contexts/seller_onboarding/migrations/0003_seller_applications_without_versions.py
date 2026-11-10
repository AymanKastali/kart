"""A Seller's submission replaces its Seller Application, so nothing counts its versions."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("seller_applications", "version")


def downgrade() -> None:
    # Every Seller Application kept starts again at the first version.
    op.add_column(
        "seller_applications",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.alter_column("seller_applications", "version", server_default=None)
