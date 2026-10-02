from backend.models.tools import ToolCall
from backend.services.game_tools import build_game_tools
from backend.services.llm_protocol import adapt_legacy_response
from backend.services.llm_response import LLMResponse
from backend.services.campaign_service import campaign_service


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