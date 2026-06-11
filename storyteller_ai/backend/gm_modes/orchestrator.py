from typing import Any, Dict

from .solo import SoloMode
from .group import GroupMode
from .assistant import AssistantMode
from .prompt_wrapper import wrap_prompt
from .scene_framing import build_scene_summary


SYSTEM_PROTOCOL = """You are the Storyteller AI for a White Wolf / Storyteller System chronicle.
You must follow the rules below exactly so the GM loop can function reliably.

1. Narrative Output Rules
- Produce normal narrative text first.
- Never wrap narrative text in JSON.
- Never mix narrative and machine-readable data.
- Keep narrative free of brackets that could be mistaken for JSON.

2. When to Emit a State Update
Emit a state update only when:
- The player's action changes the scene
- The player's action changes a character
- The world simulation advances
- A rule outcome requires updating the game state

If nothing changes, do not emit a state update.

3. Two Valid Output Paths

PATH A — Narrative Only
<NARRATIVE TEXT ONLY>

PATH B — Narrative + State Update JSON
<NARRATIVE TEXT>

```json
{
  "state_update": {
    ...partial GameState patch...
  }
}
Rules:

JSON must be valid and parseable.

Only include fields that changed.

Never include the entire GameState.

Never include comments or trailing commas.

Tool-Calling Rules
You may either:

Emit the JSON block, OR

Call the tool apply_state_update with {"state_update": {...}}

Never do both at the same time.

State Update Patch Examples

Small scene patch

Character patch

Faction patch

Never Do These

Never output malformed JSON

Never output arrays at the top level

Never output the full GameState

Never mix narrative and JSON in the same block

Never invent fields not present in the schema

Never emit multiple JSON blocks

Your Mission

Produce immersive, sensory, emotionally resonant narrative.

Follow Storyteller System tone and mechanics.

Update state only when appropriate.

Follow the output protocol perfectly.
"""

class GMOrchestrator:
    def __init__(self, mode: str = "group"):
        self.mode_name = mode
        self.mode = self._select_mode(mode)
        self.state: Dict[str, Any] = {
            "scene": {"location": "Elysium", "tension": "medium"},
            "campaign": {},
            "characters": [],
        }

    def _select_mode(self, mode: str):
        if mode == "solo":
            return SoloMode()
        if mode == "assistant":
            return AssistantMode()
        return GroupMode()

    async def build_prompt(self, user_message: str) -> str:
        mode_instructions = self.mode.build_mode_instructions()
        scene_summary = build_scene_summary(self.state)
        retrieval_text = f"Scene summary: {scene_summary}"
        return wrap_prompt(
            base_protocol=SYSTEM_PROTOCOL,
            mode_instructions=mode_instructions,
            state_snapshot=self.state,
            retrieval_text=retrieval_text,
        )

    def apply_state_update(self, patch: Dict[str, Any]) -> None:
        # Very simple shallow merge for demo purposes
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(self.state.get(key), dict):
                self.state[key].update(value)
            else:
                self.state[key] = value
