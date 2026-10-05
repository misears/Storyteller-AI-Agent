from backend.models.tools import ToolCall
from backend.services.game_tools import build_game_tools
from backend.services.llm_protocol import adapt_legacy_response
from backend.services.llm_response import LLMResponse
from backend.services.campaign_service import campaign_service
from backend.services.dice_service import dice_service


def test_legacy_provider_response_becomes_tool_call():
    response = adapt_legacy_response(LLMResponse("narration", {"state_update": {"flags": {"x": 1}}}))

    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].name == "apply_state_update"


def test_game_tool_registry_exposes_authoritative_roll():
    campaign = campaign_service.create("Tool test")
    registry = build_game_tools(campaign)

    result = registry.dispatch(ToolCall(
        id="roll-1", name="roll_dice", arguments={"expression": "1d6", "reason": "test"},
    ))

    assert result.ok is True
    assert result.result["campaign_id"] == campaign.id


def test_game_tool_dice_rolls_advance_rng_counter_without_persisting():
    campaign = campaign_service.create("Sequential tool rolls")
    staged = []
    counter = [dice_service.current_counter(campaign)]
    registry = build_game_tools(campaign, "turn-1", staged, counter)

    first = registry.dispatch(ToolCall(
        id="first", name="roll_dice", arguments={"expression": "1d10", "reason": "first"},
    ))
    second = registry.dispatch(ToolCall(
        id="second", name="roll_dice", arguments={"expression": "1d10", "reason": "second"},
    ))

    assert first.ok and second.ok
    assert staged[0]["rng"]["counter_start"] == 0
    assert staged[1]["rng"]["counter_start"] == staged[0]["rng"]["counter_end"]
    assert counter[0] == staged[1]["rng"]["counter_end"]
    assert dice_service.list(campaign)[0] == []


def test_state_update_tool_rejects_unknown_root_fields():
    registry = build_game_tools(campaign_service.create("Restricted state patch"))

    result = registry.dispatch(ToolCall(
        id="bad-patch", name="apply_state_update",
        arguments={"state_update": {"python": {"execute": "unsafe"}}},
    ))

    assert result.ok is False
    assert len(registry.audit) == 1