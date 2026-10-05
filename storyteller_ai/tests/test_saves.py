from sqlalchemy import select

from backend.services.campaign_service import campaign_service
from backend.services.save_service import save_service
from backend.services.chat_service import chat_service
from backend.services.dice_service import dice_service
from backend.models.campaign import Actor
from backend.persistence.db import create_campaign_engine
from backend.persistence.event_store import EventStore
from backend.persistence.tables import saves


def test_named_save_and_forked_load(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Save test")
    chat_service.post(campaign.id, campaign.active_branch_id, "Before save", "player")
    dice_service.roll(campaign, "1d20", "before save")
    saved = save_service.create(campaign, "before-choice")
    chat_service.post(campaign.id, campaign.active_branch_id, "After save", "player")
    dice_service.roll(campaign, "1d20", "after save")

    branch_id = save_service.load(campaign, saved["id"])
    fork = campaign.model_copy(update={"active_branch_id": branch_id})
    messages, _ = chat_service.list(campaign.id, branch_id, limit=100)
    rolls, _ = dice_service.list(fork, limit=100)
    assert branch_id != campaign.active_branch_id
    assert save_service.list(campaign)[0]["name"] == "before-choice"
    assert [message.content for message in messages][0] == "Before save"
    assert len(messages) == 2
    assert [roll.reason for roll in rolls] == ["before save"]


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


def test_game_state_tool_events_are_included_in_save_and_fork_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Tool state save")
    engine = create_campaign_engine()
    try:
        with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
            writer.append("game_state.updated", {
                "patch": {"scene": {"tension": "high"}, "flags": {"alarm": True}},
            }, Actor(kind="ai_gm"), "turn-tool-state")
    finally:
        engine.dispose()

    saved = save_service.create(campaign, "after-tool-update")

    assert saved["state"]["storyteller_state"] == {
        "scene": {"tension": "high"}, "flags": {"alarm": True},
    }
    engine = create_campaign_engine()
    try:
        with engine.connect() as connection:
            stored = connection.execute(select(saves.c.data).where(saves.c.id == saved["id"])).scalar_one()
        assert stored["state"]["storyteller_state"]["scene"]["tension"] == "high"
    finally:
        engine.dispose()

    archive = save_service.export(campaign)
    imported = save_service.import_archive(archive)
    branch_id = save_service.load(imported, save_service.list(imported)[0]["id"])
    engine = create_campaign_engine()
    try:
        imported_history = EventStore(engine).read(imported.id, branch_id)
    finally:
        engine.dispose()
    forked = imported.model_copy(update={"active_branch_id": branch_id})
    replayed = save_service.create(forked, "replayed-tool-state")
    assert any(event.type == "game_state.updated" for event in imported_history)
    assert replayed["state"]["storyteller_state"]["flags"]["alarm"] is True