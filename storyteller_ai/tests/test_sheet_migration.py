from backend.services.character_sheet_store import CharacterSheetStore
from backend.services.sheet_migration import migrate_legacy_sheets
from backend.persistence.db import create_campaign_engine, upgrade_database
from backend.persistence.tables import character_sheets
from sqlalchemy import select


def test_legacy_sheet_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    store = CharacterSheetStore(tmp_path / "legacy.json")
    sheet = store.create_sheet("fantasy-hero-player", "Aria", None)

    assert migrate_legacy_sheets(store) == 1
    assert migrate_legacy_sheets(store) == 0
    upgrade_database()
    engine = create_campaign_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(select(character_sheets.c.id)) == sheet["sheet_id"]
    finally:
        engine.dispose()