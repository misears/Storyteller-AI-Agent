import asyncio
import json
from typing import Optional

from ..gm_modes.orchestrator import GMOrchestrator
from ..models.campaign import Campaign
from ..models.tools import ToolCall, ToolResult
from ..services.game_tools import build_game_tools
from ..services.llm_client import LLMClient
from ..services.llm_utils import extract_actions, extract_state_update
from ..services.runtime_settings import runtime_settings
from uuid import uuid4


MAX_TOOL_ROUNDS = 6
MAX_TOOL_CALLS = 12


class ToolLoopLimitError(RuntimeError):
    """Raised when a model exceeds the bounded per-turn game-tool budget."""


class GMLoop:
    def __init__(self, mode: str = "group", llm_client: Optional[LLMClient] = None):
        self.mode = mode
        self.orchestrator = GMOrchestrator(mode)
        self.llm = llm_client or LLMClient()

    async def step(
        self, user_message: str, campaign: Campaign | None = None,
        turn_id: str | None = None,
    ) -> dict:
        system_prompt = await self.orchestrator.build_prompt(user_message)
        if campaign is not None:
            if getattr(self.llm, "uses_ollama", False):
                total_timeout = float(runtime_settings.get_llm()["ollama_total_timeout"])
                try:
                    async with asyncio.timeout(total_timeout):
                        return await self._step_with_tools(
                            system_prompt, user_message, campaign, turn_id,
                        )
                except TimeoutError as exc:
                    from ..services.llm_client import LLMTimeoutError
                    raise LLMTimeoutError(
                        f"Ollama tool loop exceeded the {total_timeout:g}-second turn budget. "
                        "The turn was not committed. Increase OLLAMA_TOTAL_TIMEOUT or retry the action."
                    ) from exc
            return await self._step_with_tools(system_prompt, user_message, campaign, turn_id)

        response = await self.llm.generate(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        cleaned_text, state_update = extract_state_update(response.text)
        if state_update:
            self.orchestrator.apply_state_update(state_update)

        return {"text": cleaned_text, "mode": self.mode}

    async def _step_with_tools(
        self, system_prompt: str, user_message: str, campaign: Campaign,
        turn_id: str | None,
    ) -> dict:
        pending_rolls: list[dict] = []
        counter = [0]
        registry = build_game_tools(campaign, turn_id, pending_rolls, counter)
        supports_native_tools = bool(getattr(self.llm, "supports_native_tools", False))
        tool_prompt = ""
        if not supports_native_tools:
            tool_prompt = (
                "\n\nAvailable validated game tools:\n" + "\n".join(
                    f"- {tool.name}: {tool.description}; arguments schema: "
                    f"{json.dumps(tool.parameters, sort_keys=True)}"
                    for tool in registry.specs()
                ) + "\nWhen a tool is needed, emit one final ```storyteller-actions fenced JSON block "
                "with {\"actions\":[{\"tool\":\"name\",\"arguments\":{...}}]}. "
                "After receiving tool results, provide final narration without another action block."
            )
        messages = [
            {"role": "system", "content": system_prompt + (
                "\n\nUse the supplied game tools for all dice and state changes. "
                "Wait for each tool result before narrating its outcome. "
                "Do not claim an action succeeded when its tool result reports failure."
            ) + tool_prompt},
            {"role": "user", "content": user_message},
        ]
        tool_results: list[dict] = []
        state_updates: list[dict] = []
        seen_call_ids: set[str] = set()
        total_calls = 0

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            response = await self.llm.generate_with_tools(messages, registry.specs())
            used_text_fallback = False
            if not response.tool_calls and not supports_native_tools and response.text:
                cleaned_text, actions = extract_actions(response.text)
                if actions is not None:
                    used_text_fallback = True
                    response.text = cleaned_text
                    response.tool_calls = [ToolCall(
                        id=str(uuid4()),
                        name=str(action.get("tool", "")),
                        arguments=action.get("arguments", {})
                        if isinstance(action.get("arguments", {}), dict) else {},
                    ) for action in actions]
                    response.finish_reason = "tool_calls"
            if not response.tool_calls:
                if response.finish_reason == "length":
                    raise ToolLoopLimitError("The model ran out of output budget before finishing the turn.")
                if not response.text.strip():
                    raise ToolLoopLimitError("The model returned neither a final narration nor a game-tool call.")
                return {
                    "text": response.text.strip(),
                    "mode": self.mode,
                    "tool_results": tool_results,
                    "state_updates": state_updates,
                    "dice_rolls": pending_rolls,
                }

            if round_index >= MAX_TOOL_ROUNDS:
                raise ToolLoopLimitError(f"The model exceeded the {MAX_TOOL_ROUNDS}-round game-tool limit.")
            if total_calls + len(response.tool_calls) > MAX_TOOL_CALLS:
                raise ToolLoopLimitError(f"The model exceeded the {MAX_TOOL_CALLS}-call game-tool limit.")
            total_calls += len(response.tool_calls)

            messages.append({
                "role": "assistant",
                "content": response.text or None,
                "tool_calls": [{
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                } for call in response.tool_calls],
            })
            for call in response.tool_calls:
                result = self._dispatch_tool(registry, call, seen_call_ids)
                tool_results.append(result.model_dump(mode="json"))
                if result.ok and call.name == "apply_state_update" and isinstance(result.result, dict):
                    state_updates.append(result.result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result.model_dump(mode="json")),
                })
            if not supports_native_tools and response.text.strip() and not used_text_fallback:
                return {
                    "text": response.text.strip(),
                    "mode": self.mode,
                    "tool_results": tool_results,
                    "state_updates": state_updates,
                    "dice_rolls": pending_rolls,
                }

        raise ToolLoopLimitError("The model did not finish the game-tool loop.")

    @staticmethod
    def _dispatch_tool(
        registry, call: ToolCall, seen_call_ids: set[str],
    ) -> ToolResult:
        if call.id in seen_call_ids:
            result = ToolResult(
                tool_call_id=call.id,
                name=call.name,
                ok=False,
                error="duplicate tool call id",
            )
            registry.audit.append({"call": call.model_dump(mode="json"), "result": result.model_dump(mode="json")})
            return result
        seen_call_ids.add(call.id)
        return registry.dispatch(call, actor_kind="gm")
