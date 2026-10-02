import pytest

from backend.models.tools import ToolCall, ToolSpec
from backend.services.tool_registry import ToolRegistry


def test_tool_registry_validates_authorizes_and_audits():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="add", description="Add values", authority="gm", parameters={
            "type": "object", "properties": {"left": {"type": "integer"}, "right": {"type": "integer"}},
            "required": ["left", "right"], "additionalProperties": False,
        }),
        lambda left, right: left + right,
    )

    result = registry.dispatch(ToolCall(id="1", name="add", arguments={"left": 2, "right": 3}))
    denied = registry.dispatch(ToolCall(id="2", name="add", arguments={"left": 2}), actor_kind="player")

    assert result.ok is True and result.result == 5
    assert denied.ok is False
    assert len(registry.audit) == 2


def test_duplicate_tools_are_rejected():
    registry = ToolRegistry()
    spec = ToolSpec(name="same", description="", parameters={"type": "object"})
    registry.register(spec, lambda: None)
    with pytest.raises(ValueError):
        registry.register(spec, lambda: None)