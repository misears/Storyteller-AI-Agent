from datetime import datetime, timezone

from backend.models.campaign import Campaign, PackRef
from backend.models.chat import ChatMessage
from backend.models.ruleset import SettingPack
from backend.models.state import GameState


def test_campaign_round_trip_and_schema():
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id="campaign-1",
        title="Midnight City",
        ruleset_id="freeform",
        ruleset_version="1.0",
        extra_rulesets=[PackRef(id="vampire", version="1.0")],
        setting_pack_id="noir",
        setting_pack_version="1.0",
        rng_seed_ref="seed-1",
        active_branch_id="branch-1",
        created_at=now,
        updated_at=now,
    )
    assert Campaign.model_validate_json(campaign.model_dump_json()) == campaign
    assert "properties" in Campaign.model_json_schema()
    assert campaign.table_config.max_players == 10

    other = Campaign.model_validate_json(campaign.model_dump_json())
    other.source_document_ids.append("book-1")
    assert campaign.source_document_ids == []


def test_state_chat_and_setting_pack_schemas_round_trip():
    state = GameState(campaign_id="campaign-1", branch_id="branch-1")
    message = ChatMessage(
        id="message-1", campaign_id=state.campaign_id, branch_id=state.branch_id,
        seq=1, speaker_kind="player", content="Hello", created_at=datetime.now(timezone.utc),
    )
    setting = SettingPack(
        id="noir", version="1.0", name="Noir", compatible_rulesets=["freeform"],
        genre=["mystery"], tone=["dark"], prompt_digest="Rain on the avenue.",
    )
    for model in (state, message, setting):
        assert type(model).model_validate_json(model.model_dump_json()) == model
        assert "properties" in type(model).model_json_schema()