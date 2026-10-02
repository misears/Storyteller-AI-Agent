"""Add database-backed character sheet compatibility tables."""

from alembic import op

from backend.persistence.tables import character_sheets, sheet_versions


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    character_sheets.create(op.get_bind())
    sheet_versions.create(op.get_bind())


def downgrade() -> None:
    sheet_versions.drop(op.get_bind())
    character_sheets.drop(op.get_bind())