from ..models.campaign import Actor, Campaign
from ..models.tools import ToolSpec
from .dice_service import dice_service
from .tool_registry import ToolRegistry


def build_game_tools(
    campaign: Campaign,
    turn_id: str | None = None,
    pending_rolls: list[dict] | None = None,
    counter: list[int] | None = None,
) -> ToolRegistry:
    pending_rolls = pending_rolls if pending_rolls is not None else []
    counter = counter if counter is not None else [dice_service.current_counter(campaign)]
    registry = ToolRegistry()

    def prepare_roll(expression, reason, target=None, character_id=None):
        roll = dice_service.prepare_roll(
            campaign, expression, reason, Actor(kind="ai_gm"), character_id, target,
            turn_id=turn_id, counter_start=counter[0],
        )
        counter[0] = roll.rng.counter_end
        prepared = roll.model_dump(mode="json")
        pending_rolls.append(prepared)
        return prepared

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
        prepare_roll,
    )
    registry.register(
        ToolSpec(
            name="apply_state_update", description="Apply an approved state patch.",
            authority="gm", parameters={
                "type": "object", "properties": {"state_update": {
                    "type": "object",
                    "properties": {
                        "scene": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "location": {"type": "string"},
                                "description": {"type": "string"},
                                "kind": {"type": "string", "enum": [
                                    "exploration", "social", "combat", "downtime", "montage",
                                ]},
                                "tension": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                                "present_character_ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "additionalProperties": False,
                        },
                        "campaign": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "setting": {"type": "string"},
                                "document_ids": {"type": "array", "items": {"type": "string"}},
                                "campaign_genres": {"type": "array", "items": {"type": "string"}},
                            },
                            "additionalProperties": False,
                        },
                        "characters": {"type": "array", "items": {"type": "object"}},
                        "flags": {"type": "object"},
                        "trackers": {"type": "object"},
                    },
                    "additionalProperties": False,
                }},
                "required": ["state_update"], "additionalProperties": False,
            },
        ),
        lambda state_update: state_update,
    )
    return registry