"""Create campaign event and chat projection tables."""

from alembic import op

from backend.persistence.tables import branches, campaigns, chat_messages, events, turns


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (campaigns, branches, events, turns, chat_messages):
        table.create(op.get_bind())


def downgrade() -> None:
    for table in (chat_messages, turns, events, branches, campaigns):
        table.drop(op.get_bind())