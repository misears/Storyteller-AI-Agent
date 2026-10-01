from sqlalchemy import select

from .character_sheet_store import CharacterSheetStore
from .app_paths import get_data_dir
from ..persistence.db import create_campaign_engine, upgrade_database
from ..persistence.tables import character_sheets


def migrate_legacy_sheets(store: CharacterSheetStore | None = None) -> int:
    legacy = store or CharacterSheetStore(get_data_dir() / "character_sheets.json")
    upgrade_database()
    engine = create_campaign_engine()
    migrated = 0
    try:
        with engine.begin() as connection:
            for sheet in legacy.list_sheets():
                values = {
                    "id": sheet["sheet_id"], "character_id": sheet["sheet_id"],
                    "ruleset_id": sheet.get("template_key", "legacy"),
                    "ruleset_version": "legacy", "version": sheet.get("version", 1),
                    "data": sheet.get("fields", {}), "derived": {},
                    "updated_at": sheet.get("updated_at", ""),
                    "updated_by_kind": "system", "updated_by_id": None,
                }
                if connection.scalar(select(character_sheets.c.id).where(character_sheets.c.id == values["id"])):
                    continue
                connection.execute(character_sheets.insert().values(**values))
                migrated += 1
    finally:
        engine.dispose()
    return migrated