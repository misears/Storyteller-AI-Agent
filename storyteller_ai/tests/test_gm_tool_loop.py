import json
import asyncio

import pytest

from backend.engines.gm_loop import GMLoop, ToolLoopLimitError
from backend.gm_modes.orchestrator import GMOrchestrator
from backend.models.tools import ProviderResponse, ToolCall
from backend.services.campaign_service import campaign_service
from backend.services.dice_service import dice_service
from backend.services.llm_client import LLMTimeoutError
from backend.services.runtime_settings import runtime_settings


def test_all_gm_modes_build_prompts_without_unfilled_state_placeholders():
    async def build_prompt(mode):
        return await GMOrchestrator(mode).build_prompt("The player looks around.")

    for mode in ("solo", "group", "assistant"):
        prompt = asyncio.run(build_prompt(mode))
        assert "...partial GameState patch..." not in prompt
        assert "State Update Patch Examples" not in prompt
        assert "Do not invent dice results" in prompt


def test_legacy_state_patch_deep_merges_allowed_fields_and_rejects_unknown_roots():
    orchestrator = GMOrchestrator("group")
    orchestrator.apply_state_update({"scene": {"tension": "high"}, "flags": {"alarm": True}})

    assert orchestrator.state["scene"] == {"location": "Elysium", "tension": "high"}
    assert orchestrator.state["flags"] == {"alarm": True}
    with pytest.raises(ValueError, match="unsupported fields"):
        orchestrator.apply_state_update({"python": {"execute": "unsafe"}})
    with pytest.raises(ValueError, match="unsupported fields"):
        orchestrator.apply_state_update({"scene": {"arbitrary": "value"}})


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def generate_with_tools(self, messages, tools):
        self.requests.append((messages, tools))
        return self.responses.pop(0)


def test_tool_loop_returns_validated_results_to_model_and_stages_state():
    patch = {"scene": {"tension": "high"}}
    llm = ScriptedLLM([
        ProviderResponse(tool_calls=[ToolCall(
            id="state-1", name="apply_state_update", arguments={"state_update": patch},
        )], finish_reason="tool_calls"),
        ProviderResponse(text="The room grows tense."),
    ])
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Tool feedback")

    result = __import__("asyncio").run(loop.step("Look around", campaign, "turn-1"))

    assert result["text"] == "The room grows tense."
    assert result["state_updates"] == [patch]
    assert loop.orchestrator.state["scene"]["tension"] == "medium"
    tool_messages = [message for message in llm.requests[1][0] if message["role"] == "tool"]
    assert len(tool_messages) == 1
    assert json.loads(tool_messages[0]["content"])["result"] == patch
    assert any(tool.name == "roll_dice" for tool in llm.requests[0][1])


def test_invalid_state_tool_arguments_are_rejected_without_mutation():
    llm = ScriptedLLM([
        ProviderResponse(tool_calls=[ToolCall(
            id="invalid-state", name="apply_state_update",
            arguments={"state_update": "not an object"},
        )], finish_reason="tool_calls"),
        ProviderResponse(text="I cannot apply that update."),
    ])
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Invalid state tool")

    result = __import__("asyncio").run(loop.step("Change the scene", campaign, "turn-2"))

    assert result["state_updates"] == []
    assert result["tool_results"][0]["ok"] is False
    assert loop.orchestrator.state["scene"]["tension"] == "medium"


def test_non_native_provider_fenced_action_is_validated_then_narrated():
    class FencedActionLLM:
        supports_native_tools = False

        def __init__(self):
            self.requests = []

        async def generate_with_tools(self, messages, tools):
            self.requests.append(messages)
            if len(self.requests) == 1:
                return ProviderResponse(text=(
                    "The action needs a state change.\n"
                    "```storyteller-actions\n"
                    '{"actions":[{"tool":"apply_state_update","arguments":'
                    '{"state_update":{"scene":{"tension":"high"}}}}]}\n'
                    "```"
                ))
            return ProviderResponse(text="The room grows tense.")

    llm = FencedActionLLM()
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Legacy action fallback")

    result = asyncio.run(loop.step("Raise the tension", campaign, "turn-fallback"))

    assert result["text"] == "The room grows tense."
    assert result["state_updates"] == [{"scene": {"tension": "high"}}]
    tool_messages = [message for message in llm.requests[1] if message["role"] == "tool"]
    assert len(tool_messages) == 1
    assert '"ok": true' in tool_messages[0]["content"]


def test_dice_tool_is_server_prepared_but_not_persisted_before_turn_commit():
    llm = ScriptedLLM([
        ProviderResponse(tool_calls=[ToolCall(
            id="roll-1", name="roll_dice",
            arguments={"expression": "1d10", "reason": "test uncertainty"},
        )], finish_reason="tool_calls"),
        ProviderResponse(text="The result changes the scene."),
    ])
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Staged dice tool")

    result = __import__("asyncio").run(loop.step("Try the uncertain action", campaign, "turn-3"))

    assert len(result["dice_rolls"]) == 1
    assert result["dice_rolls"][0]["turn_id"] == "turn-3"
    assert result["tool_results"][0]["ok"] is True
    rolls, _ = dice_service.list(campaign)
    assert rolls == []


def test_duplicate_tool_call_id_is_not_dispatched_twice():
    call = ToolCall(
        id="same-id", name="apply_state_update",
        arguments={"state_update": {"scene": {"tension": "high"}}},
    )
    llm = ScriptedLLM([
        ProviderResponse(tool_calls=[call, call], finish_reason="tool_calls"),
        ProviderResponse(text="The update was processed once."),
    ])
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Duplicate tool ID")

    result = __import__("asyncio").run(loop.step("Raise the tension", campaign, "turn-4"))

    assert [item["ok"] for item in result["tool_results"]] == [True, False]
    assert result["state_updates"] == [{"scene": {"tension": "high"}}]


def test_tool_loop_stops_at_six_round_limit_without_returning_staged_updates():
    llm = ScriptedLLM([
        ProviderResponse(tool_calls=[ToolCall(
            id=f"state-{index}", name="apply_state_update",
            arguments={"state_update": {"scene": {"tension": "high"}}},
        )], finish_reason="tool_calls")
        for index in range(7)
    ])
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Tool loop cap")

    with pytest.raises(ToolLoopLimitError, match="6-round"):
        __import__("asyncio").run(loop.step("Raise the tension", campaign, "turn-5"))

    assert len(llm.requests) == 7
    assert loop.orchestrator.state["scene"]["tension"] == "medium"


def test_ollama_tool_rounds_share_one_total_turn_budget(monkeypatch):
    monkeypatch.setattr(runtime_settings, "_overrides", {})
    monkeypatch.setenv("OLLAMA_TOTAL_TIMEOUT", "1")

    class SlowOllamaLoop:
        uses_ollama = True
        calls = 0

        async def generate_with_tools(self, messages, tools):
            self.calls += 1
            await asyncio.sleep(0.6)
            if self.calls == 1:
                return ProviderResponse(tool_calls=[ToolCall(
                    id="first-round",
                    name="apply_state_update",
                    arguments={"state_update": {"scene": {"tension": "high"}}},
                )], finish_reason="tool_calls")
            return ProviderResponse(text=f"round {self.calls}")

    llm = SlowOllamaLoop()
    loop = GMLoop(llm_client=llm)
    campaign = campaign_service.create("Total tool-loop timeout")

    with pytest.raises(LLMTimeoutError, match="tool loop exceeded"):
        asyncio.run(loop.step("Long action", campaign, "turn-timeout"))
    assert llm.calls == 2
