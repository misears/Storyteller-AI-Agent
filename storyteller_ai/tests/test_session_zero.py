from backend.services.bible_service import bible_service
from backend.services.campaign_service import campaign_service
from backend.services.session_zero_service import session_zero_service


def test_session_zero_seeds_opening_scene_and_session_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Session Zero")
    bible_service.generate(campaign)
    persisted = campaign_service.get(campaign.id)
    seeded = session_zero_service.complete(persisted)
    session = session_zero_service.start_session(persisted, ["player-1"])
    ended = session_zero_service.end_session(persisted, session.id, "The night begins.")

    assert seeded["scene_id"]
    assert session.attendee_player_ids == ["player-1"]
    assert ended.recap == "The night begins."