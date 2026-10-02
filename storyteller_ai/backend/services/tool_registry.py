from collections.abc import Callable
from typing import Any

from jsonschema import ValidationError, validate

from ..models.tools import ToolCall, ToolResult, ToolSpec


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}
        self.audit: list[dict[str, Any]] = []

    def register(self, spec: ToolSpec, handler: Callable[..., Any]) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def dispatch(self, call: ToolCall, actor_kind: str = "gm", **context: Any) -> ToolResult:
        entry = self._tools.get(call.name)
        if entry is None:
            return ToolResult(tool_call_id=call.id, name=call.name, ok=False, error="unknown tool")
        spec, handler = entry
        if not self._authorized(spec.authority, actor_kind):
            result = ToolResult(tool_call_id=call.id, name=call.name, ok=False, error="tool not authorized")
        else:
            try:
                validate(call.arguments, spec.parameters)
                result = ToolResult(
                    tool_call_id=call.id, name=call.name, ok=True,
                    result=handler(**call.arguments, **context),
                )
            except (ValidationError, TypeError, ValueError, KeyError) as exc:
                result = ToolResult(tool_call_id=call.id, name=call.name, ok=False, error=str(exc))
        self.audit.append({"call": call.model_dump(mode="json"), "result": result.model_dump(mode="json")})
        return result

    @staticmethod
    def _authorized(required: str, actor_kind: str) -> bool:
        return required == "system" and actor_kind == "system" or required in {"gm", actor_kind}