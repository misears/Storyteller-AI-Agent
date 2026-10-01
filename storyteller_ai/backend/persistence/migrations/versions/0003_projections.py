"""Add player, membership, session and scene projections."""

from alembic import op

from backend.persistence.tables import memberships, play_sessions, players, scenes


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (players, memberships, play_sessions, scenes):
        table.create(op.get_bind())


def downgrade() -> None:
    for table in (scenes, play_sessions, memberships, players):
        table.drop(op.get_bind())