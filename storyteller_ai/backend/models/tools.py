from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    authority: Literal["player", "host", "gm", "system"] = "gm"


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    ok: bool
    result: Any = None
    error: str | None = None


class ProviderResponse(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: Literal["stop", "tool_calls", "length", "error"] = "stop"
    usage: dict[str, int] | None = None