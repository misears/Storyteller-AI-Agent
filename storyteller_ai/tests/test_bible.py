from backend.services.bible_service import bible_service
from backend.services.campaign_service import campaign_service


def test_bible_generation_edit_and_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = campaign_service.create("The Midnight City")
    generated = bible_service.generate(campaign)
    edited = bible_service.edit(campaign, "premise", "A city bargains with its shadows.")

    assert generated.acts
    assert edited.premise == "A city bargains with its shadows."
    assert bible_service.get(campaign_service.get(campaign.id)).opening_situation