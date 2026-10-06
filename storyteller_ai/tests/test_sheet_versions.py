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


def test_advancement_requires_ai_review_and_human_approval(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    sheet = store.create_sheet("fantasy-hero-player", "Aria", None)
    sheet = store.link_campaign(sheet["sheet_id"], "campaign-1", 1)
    request = store.propose_advancement(sheet["sheet_id"], "award", 5, {}, "Completed the session", sheet["version"])
    assert sheet["experience"]["available"] == 0
    with pytest.raises(SheetValidationError):
        store.decide_advancement(sheet["sheet_id"], request["id"], True, "Storyteller", "Session award")
    store.record_ai_review(sheet["sheet_id"], request["id"], {"recommendation": "approve", "reason": "Session award supported", "citations": []})
    result = store.decide_advancement(sheet["sheet_id"], request["id"], True, "Storyteller", "Session award")
    assert result["experience"] == {"earned": 5, "spent": 0, "available": 5}
    with pytest.raises(SheetValidationError):
        store.decide_advancement(sheet["sheet_id"], request["id"], True, "Storyteller", "Repeat award")
    persisted = CharacterSheetStore(tmp_path / "sheets.json").get_sheet(sheet["sheet_id"])
    assert persisted["experience"]["available"] == 5
    assert persisted["advancement_requests"][0]["status"] == "approved"


def test_advancement_spends_xp_and_applies_sheet_once(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    sheet = store.create_sheet("fantasy-hero-player", "Aria", None)
    sheet = store.link_campaign(sheet["sheet_id"], "campaign-1", 1)
    award = store.propose_advancement(sheet["sheet_id"], "award", 8, {}, "Session award", sheet["version"])
    review = {"recommendation": "approve", "reason": "Supported by rules", "citations": []}
    store.record_ai_review(sheet["sheet_id"], award["id"], review)
    sheet = store.decide_advancement(sheet["sheet_id"], award["id"], True, "GM", "Confirmed")
    request = store.propose_advancement(sheet["sheet_id"], "spend", 3, {"vitality": 11}, "Training", sheet["version"])
    assert sheet["fields"]["vitality"] == 10
    store.record_ai_review(sheet["sheet_id"], request["id"], review)
    updated = store.decide_advancement(sheet["sheet_id"], request["id"], True, "GM", "Approved training")
    assert updated["fields"]["vitality"] == 11
    assert updated["experience"] == {"earned": 8, "spent": 3, "available": 5}
    with pytest.raises(SheetValidationError):
        store.update_sheet(sheet["sheet_id"], fields={"vitality": 99})
    with pytest.raises(SheetValidationError):
        store.revert_sheet(sheet["sheet_id"], 1)


def test_advancement_rejects_stale_and_unaffordable_changes(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    sheet = store.create_sheet("fantasy-hero-player", "Aria", None)
    sheet = store.link_campaign(sheet["sheet_id"], "campaign-1", 1)
    review = {"recommendation": "approve", "reason": "Reviewed", "citations": []}
    spend = store.propose_advancement(sheet["sheet_id"], "spend", 100, {"vitality": 12}, "Training", sheet["version"])
    store.record_ai_review(sheet["sheet_id"], spend["id"], review)
    with pytest.raises(SheetValidationError):
        store.decide_advancement(sheet["sheet_id"], spend["id"], True, "GM", "Confirmed")
    award = store.propose_advancement(sheet["sheet_id"], "award", 2, {}, "Session award", sheet["version"])
    store.record_ai_review(sheet["sheet_id"], award["id"], review)
    store.decide_advancement(sheet["sheet_id"], award["id"], True, "GM", "Confirmed")
    with pytest.raises(SheetConflictError):
        store.decide_advancement(sheet["sheet_id"], spend["id"], True, "GM", "Stale approval")
    assert sheet["experience"]["available"] == 2
    assert sheet["fields"]["vitality"] == 10


def test_rejection_and_invalid_xp_leave_saved_sheet_unchanged(tmp_path):
    store = CharacterSheetStore(tmp_path / "sheets.json")
    sheet = store.create_sheet("fantasy-hero-player", "Aria", None)
    sheet = store.link_campaign(sheet["sheet_id"], "campaign-1", 1)
    for xp in [-1, True, 1.5]:
        with pytest.raises(SheetValidationError):
            store.propose_advancement(sheet["sheet_id"], "award", xp, {}, "Award", sheet["version"])
    request = store.propose_advancement(sheet["sheet_id"], "spend", 5, {"vitality": 11}, "Training", sheet["version"])
    result = store.decide_advancement(sheet["sheet_id"], request["id"], False, "GM", "Not eligible yet")
    assert result["experience"]["available"] == 0
    assert result["fields"]["vitality"] == 10
    assert result["version"] == 2
    assert result["advancement_requests"][0]["status"] == "rejected"