"""Add the dice roll projection."""

from alembic import op

from backend.persistence.tables import dice_rolls


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dice_rolls.create(op.get_bind())


def downgrade() -> None:
    dice_rolls.drop(op.get_bind())