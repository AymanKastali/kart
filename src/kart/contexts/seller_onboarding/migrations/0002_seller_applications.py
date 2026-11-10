"""Each Seller's one Seller Application, keyed by its Account."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seller_applications",
        sa.Column("account_id", sa.Uuid, primary_key=True),
        sa.Column("seller_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("legal_name", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("trade_licence_number", sa.String, nullable=False),
        sa.Column("vat_number", sa.String, nullable=False),
        sa.Column("iban", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("seller_applications")
