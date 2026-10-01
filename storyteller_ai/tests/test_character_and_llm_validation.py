import pytest

from backend.models.campaign import Actor
from backend.models.character import Character
from backend.rules.registry import RulesetRegistry
from backend.services.character_service import build_character_sheet, build_npc_sheet
from backend.services.llm_validation import validate_narration
from backend.services.runtime_settings import RuntimeSettings


def test_ruleset_driven_sheet_validation_and_derived_values():
    ruleset = RulesetRegistry().get("pbta-generic")
    character = Character(
        id="character-1", campaign_id="campaign-1", kind="pc", name="Kira",
        sheet_id="sheet-1", created_in_turn_id=None,
    )
    sheet = build_character_sheet(ruleset, character, {"attributes": {"cool": 2}, "harm": 0}, Actor(kind="player"))

    assert sheet.ruleset_id == "pbta-generic"
    assert sheet.version == 1


def test_fabricated_rolls_are_rejected():
    with pytest.raises(ValueError):
        validate_narration("You rolled 17 successes.", [{"total": 9, "successes": 1}])
    validate_narration("You rolled 9.", [{"total": 9}])


def test_npc_tier_requires_ruleset_fields():
    ruleset = RulesetRegistry().get("vtm-revised")
    character = Character(id="npc-1", campaign_id="campaign-1", kind="npc", name="Guard", sheet_id="sheet-1")
    sheet = build_npc_sheet(
        ruleset, character, "minion", {"name": "Guard", "health": 3}, Actor(kind="ai_gm")
    )

    assert sheet.ruleset_id == "vtm-revised"


def test_model_profiles_are_role_scoped():
    settings = RuntimeSettings()
    profile = settings.update_profile("storyteller", {"model": "mock", "supports_tools": True})

    assert profile["model"] == "mock"
    assert settings.get_profiles()["storyteller"]["supports_tools"] is True