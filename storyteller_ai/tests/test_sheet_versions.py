import pytest

from backend.services.character_sheet_store import (
    CharacterSheetStore, SheetConflictError, SheetValidationError,
)


def test_sheet_versions_lock_history_and_revert(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    created = store.create_sheet("fantasy-hero-player", "Aria", None, {"vitality": 8})
    updated = store.update_sheet(created["sheet_id"], fields={"vitality": 6}, expected_version=1)

    assert updated["version"] == 2
    assert len(store.list_history(created["sheet_id"])) == 1
    with pytest.raises(SheetConflictError):
        store.update_sheet(created["sheet_id"], fields={"vitality": 1}, expected_version=1)

    reverted = store.revert_sheet(created["sheet_id"], 1, expected_version=2)
    assert reverted["version"] == 3
    assert reverted["fields"]["vitality"] == 8


def test_sheet_field_schema_rejects_wrong_types(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    created = store.create_sheet("fantasy-hero-player", "Aria", None)

    with pytest.raises(SheetValidationError):
        store.update_sheet(created["sheet_id"], fields={"vitality": "high"})