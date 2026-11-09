"""Give the throwaway context an outbox, as a real context's revision would."""

from alembic import op

from kart.shared.outbox import create_outbox_table

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_outbox_table()


def downgrade() -> None:
    op.drop_table("outbox")
