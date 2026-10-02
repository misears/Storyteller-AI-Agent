"""Add named save snapshots."""

from alembic import op

from backend.persistence.tables import saves


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    saves.create(op.get_bind())


def downgrade() -> None:
    saves.drop(op.get_bind())