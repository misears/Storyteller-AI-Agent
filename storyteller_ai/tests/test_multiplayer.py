import pytest

from backend.services.campaign_service import campaign_service
from backend.services.multiplayer_service import multiplayer_service


def test_local_players_join_select_characters_and_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("Table")
    players = [multiplayer_service.join(campaign.id, campaign.active_branch_id, f"P{index}") for index in range(10)]

    membership = multiplayer_service.select_character(
        campaign.id, campaign.active_branch_id, players[0].id, "character-1",
    )
    multiplayer_service.set_status(campaign.id, campaign.active_branch_id, players[1].id, "away")

    assert membership.active_character_id == "character-1"
    replacement = multiplayer_service.join(campaign.id, campaign.active_branch_id, "P10")

    assert replacement.display_name == "P10"
    with pytest.raises(ValueError):
        multiplayer_service.join(campaign.id, campaign.active_branch_id, "P11")