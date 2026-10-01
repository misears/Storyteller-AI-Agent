from ..models.campaign import Actor, Campaign
from ..models.tools import ToolSpec
from .dice_service import dice_service
from .tool_registry import ToolRegistry


def build_game_tools(campaign: Campaign) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="roll_dice", description="Resolve an uncertain action with server dice.",
            authority="gm", parameters={
                "type": "object", "properties": {
                    "expression": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                    "target": {"type": "integer"},
                    "character_id": {"type": "string"},
                }, "required": ["expression", "reason"], "additionalProperties": False,
            },
        ),
        lambda expression, reason, target=None, character_id=None: dice_service.roll(
            campaign, expression, reason, Actor(kind="ai_gm"), character_id, target,
        ).model_dump(mode="json"),
    )
    registry.register(
        ToolSpec(
            name="apply_state_update", description="Apply an approved state patch.",
            authority="gm", parameters={
                "type": "object", "properties": {"state_update": {"type": "object"}},
                "required": ["state_update"], "additionalProperties": False,
            },
        ),
        lambda state_update: state_update,
    )
    return registry