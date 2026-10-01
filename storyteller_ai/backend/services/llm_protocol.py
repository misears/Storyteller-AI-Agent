from typing import Protocol

from ..models.tools import ProviderResponse, ToolCall
from .llm_response import LLMResponse


class Provider(Protocol):
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse: ...


def adapt_legacy_response(response: LLMResponse) -> ProviderResponse:
    tool_calls: list[ToolCall] = []
    state_update = response.metadata.get("state_update")
    if isinstance(state_update, dict):
        tool_calls.append(ToolCall(
            id="legacy-state-update", name="apply_state_update",
            arguments={"state_update": state_update},
        ))
    return ProviderResponse(
        text=response.text, tool_calls=tool_calls,
        finish_reason="tool_calls" if tool_calls else "stop",
    )