from backend.services.campaign_service import campaign_service
from backend.services.save_service import save_service
from backend.services.chat_service import chat_service


def test_named_save_and_forked_load(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Save test")
    chat_service.post(campaign.id, campaign.active_branch_id, "Before save", "player")
    saved = save_service.create(campaign, "before-choice")
    chat_service.post(campaign.id, campaign.active_branch_id, "After save", "player")

    branch_id = save_service.load(campaign, saved["id"])
    assert branch_id != campaign.active_branch_id
    assert save_service.list(campaign)[0]["name"] == "before-choice"


def test_export_is_guarded_and_contains_no_pdf_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Export test")
    archive = save_service.export(campaign)
    inspected = save_service.inspect_export(archive)

    assert inspected["campaign"]["id"] == campaign.id
    assert inspected["event_count"] >= 1


def test_export_import_creates_independent_campaign(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Round trip")
    archive = save_service.export(campaign)

    imported = save_service.import_archive(archive)

    assert imported.id != campaign.id
    assert campaign_service.get(imported.id).title == "Round trip"