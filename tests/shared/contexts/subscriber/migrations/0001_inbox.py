"""Give the subscriber context an inbox, as a real context's revision would, and a table its
handlers write to."""

from alembic import op
from sqlalchemy import Column, Uuid

from kart.shared.inbox import create_inbox_table

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_inbox_table()
    # Not unique, so a handler that ran twice leaves two rows.
    op.create_table("handled", Column("event_id", Uuid, nullable=False))


def downgrade() -> None:
    op.drop_table("handled")
    op.drop_table("inbox")
