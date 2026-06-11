#!/usr/bin/env python
"""
Storyteller AI — Backend Bootstrap Script (Option C1 / Version 3, interactive overwrite)

Usage:
    python bootstrap_backend.py

This will:
- Create the full backend folder structure
- Populate all files with working code (core modules fully implemented, others as stubs)
- Ask before overwriting any existing file
"""

import os
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "storyteller_ai" / "backend"


def ask_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    while True:
        ans = input(f"File exists: {path}\nOverwrite? [y/N]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            return False


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_file(rel_path: str, content: str):
    path = ROOT / rel_path
    ensure_dir(path.parent)
    if not ask_overwrite(path):
        print(f"Skipping {path}")
        return
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")
    print(f"Wrote {path}")


# -----------------------------
# FILE CONTENTS
# -----------------------------

FILES = {}

# main.py
FILES["storyteller_ai/backend/main.py"] = """
from fastapi import FastAPI
from .routers import gm, sessions

app = FastAPI(title="Storyteller AI Backend")

app.include_router(gm.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
"""

# routers/gm.py
FILES["storyteller_ai/backend/routers/gm.py"] = """
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.session_manager import session_manager

router = APIRouter(prefix="/gm", tags=["gm"])


class GMStepRequest(BaseModel):
    session_id: str
    message: str


@router.post("/step")
async def gm_step(payload: GMStepRequest):
    try:
        loop = session_manager.get_loop(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await loop.step(payload.message)
    return result
"""

# routers/sessions.py
FILES["storyteller_ai/backend/routers/sessions.py"] = """
from fastapi import APIRouter
from pydantic import BaseModel
from ..services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    mode: str = "group"


@router.post("/create")
def create_session(payload: CreateSessionRequest):
    session_id = session_manager.create_session(payload.mode)
    return {"session_id": session_id, "mode": payload.mode}
"""

# routers/tools.py (stub)
FILES["storyteller_ai/backend/routers/tools.py"] = """
from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/ping")
async def ping():
    return {"status": "tools-ok"}
"""

# routers/dashboard.py (stub)
FILES["storyteller_ai/backend/routers/dashboard.py"] = """
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/ping")
async def ping():
    return {"status": "dashboard-ok"}
"""

# gm_modes/__init__.py
FILES["storyteller_ai/backend/gm_modes/__init__.py"] = """
from .orchestrator import GMOrchestrator

__all__ = ["GMOrchestrator"]
"""

# gm_modes/solo.py (stub behavior)
FILES["storyteller_ai/backend/gm_modes/solo.py"] = """
class SoloMode:
    name = "solo"

    def build_mode_instructions(self) -> str:
        return (
            "You are running a solo chronicle for a single player. "
            "Focus on introspection, personal horror, and tight pacing."
        )
"""

# gm_modes/group.py
FILES["storyteller_ai/backend/gm_modes/group.py"] = """
class GroupMode:
    name = "group"

    def build_mode_instructions(self) -> str:
        return (
            "You are running a group chronicle for multiple players. "
            "Balance spotlight, politics, and shared tension."
        )
"""

# gm_modes/assistant.py
FILES["storyteller_ai/backend/gm_modes/assistant.py"] = """
class AssistantMode:
    name = "assistant"

    def build_mode_instructions(self) -> str:
        return (
            "You are a Storyteller's assistant. Offer suggestions, hooks, and consequences, "
            "but do not override the human GM."
        )
"""

# gm_modes/prompt_wrapper.py
FILES["storyteller_ai/backend/gm_modes/prompt_wrapper.py"] = """
from typing import Any, Dict


def wrap_prompt(base_protocol: str, mode_instructions: str, state_snapshot: Dict[str, Any], retrieval_text: str) -> str:
    state_str = repr(state_snapshot)
    return f\"\"\"{base_protocol}

=== GM MODE INSTRUCTIONS ===
{mode_instructions}

=== CURRENT GAME STATE (SNAPSHOT) ===
{state_str}

=== RETRIEVED CONTEXT ===
{retrieval_text}

Follow the protocol exactly.
\"\"\"
"""

# gm_modes/scene_framing.py (stub)
FILES["storyteller_ai/backend/gm_modes/scene_framing.py"] = """
from typing import Dict, Any


def build_scene_summary(state: Dict[str, Any]) -> str:
    scene = state.get("scene", {})
    location = scene.get("location", "an unspecified location")
    tension = scene.get("tension", "unknown")
    return f"Current scene is at {location}, with tension level: {tension}."
"""

FILES["storyteller_ai/backend/gm_modes/orchestrator.py"] = """
from typing import Any, Dict

from .solo import SoloMode
from .group import GroupMode
from .assistant import AssistantMode
from .prompt_wrapper import wrap_prompt
from .scene_framing import build_scene_summary


SYSTEM_PROTOCOL = \"\"\"You are the Storyteller AI for a White Wolf / Storyteller System chronicle.
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
\"\"\"

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
"""

FILES["storyteller_ai/backend/engines/gm_loop.py"] = """
from ..gm_modes.orchestrator import GMOrchestrator
from ..services.llm_client import LLMClient
from ..services.llm_utils import extract_state_update

class GMLoop:
    def __init__(self, mode: str = "group"):
        self.mode = mode
        self.orchestrator = GMOrchestrator(mode)
        self.llm = LLMClient()

    async def step(self, user_message: str) -> dict:
        system_prompt = await self.orchestrator.build_prompt(user_message)
        response = await self.llm.generate(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        cleaned_text, state_update = extract_state_update(response.text)
        if state_update:
            self.orchestrator.apply_state_update(state_update)

        return {"text": cleaned_text, "mode": self.mode}
"""

# engines stubs
ENGINE_STUB = """
\"\"\"Stub engine module for Storyteller AI.\"\"\"


def placeholder():
    return "engine-ok"
"""
for name in [
    "faction_ai.py",
    "faction_engine.py",
    "city_map.py",
    "npc_memory.py",
    "secrecy_tracker.py",
    "chronicle_starter.py",
    "turn_engine.py",
    "scene_predictor.py",
    "pc_builder.py",
    "combat_engine.py",
    "dice_pool.py",
]:
    FILES[f"storyteller_ai/backend/engines/{name}"] = ENGINE_STUB

# services/llm_response.py
FILES["storyteller_ai/backend/services/llm_response.py"] = """
from typing import Optional, Dict, Any


class LLMResponse:
    def __init__(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        self.text = text
        self.metadata = metadata or {}
"""

# services/retry.py
FILES["storyteller_ai/backend/services/retry.py"] = """
import asyncio
from typing import Any, Awaitable, Callable, Tuple, Type


async def with_retries(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    retries: int = 3,
    base_delay: float = 0.5,
    retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except retry_exceptions:
            attempt += 1
            if attempt > retries:
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
"""

# services/llm_utils.py
FILES["storyteller_ai/backend/services/llm_utils.py"] = """
import json
import re
from typing import Any, Dict, Optional, Tuple

JSON_BLOCK_RE = re.compile(r"\\{.*\\}", re.DOTALL)


def extract_state_update(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    match = JSON_BLOCK_RE.search(text)
    if not match:
        return text, None

    json_str = match.group(0)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return text, None

    state_update = data.get("state_update")
    cleaned = text.replace(json_str, "").strip()
    return cleaned, state_update
"""

# services/llm_client.py
FILES["storyteller_ai/backend/services/llm_client.py"] = """
import os
from typing import AsyncGenerator

from .llm_response import LLMResponse
from .retry import with_retries

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

STATE_UPDATE_TOOL = {
    "name": "apply_state_update",
    "description": "Apply a partial JSON patch to the current GameState.",
    "parameters": {
        "type": "object",
        "properties": {
            "state_update": {"type": "object"}
        },
        "required": ["state_update"],
    },
}

openai_client = None
anthropic_client = None

if LLM_PROVIDER == "openai":
    from openai import AsyncOpenAI
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elif LLM_PROVIDER == "anthropic":
    import anthropic
    anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class LLMClient:
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        if LLM_PROVIDER == "openai":
            return await with_retries(self._openai, system_prompt, user_message)
        if LLM_PROVIDER == "anthropic":
            return await with_retries(self._anthropic, system_prompt, user_message)
        raise RuntimeError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    async def _openai(self, system_prompt: str, user_message: str) -> LLMResponse:
        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            tools=[{"type": "function", "function": STATE_UPDATE_TOOL}],
            tool_choice="auto",
            temperature=0.7,
        )

        choice = response.choices[0]
        metadata = {}

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                if tool_call.function.name == "apply_state_update":
                    import json
                    args = json.loads(tool_call.function.arguments)
                    metadata["state_update"] = args.get("state_update")

        text = choice.message.content or ""
        return LLMResponse(text=text, metadata=metadata)

    async def _anthropic(self, system_prompt: str, user_message: str) -> LLMResponse:
        response = await anthropic_client.messages.create(
            model=LLM_MODEL,
            max_tokens=800,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[STATE_UPDATE_TOOL],
            tool_choice={"type": "auto"},
        )

        metadata = {}
        text_parts = []

        for block in response.content:
            if block.type == "tool_use" and block.name == "apply_state_update":
                metadata["state_update"] = block.input.get("state_update")
            elif block.type == "text":
                text_parts.append(block.text)

        return LLMResponse(text="\\n".join(text_parts), metadata=metadata)

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        if LLM_PROVIDER == "openai":
            async for chunk in self._openai_stream(system_prompt, user_message):
                yield chunk
        elif LLM_PROVIDER == "anthropic":
            async for chunk in self._anthropic_stream(system_prompt, user_message):
                yield chunk
        else:
            raise RuntimeError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    async def _openai_stream(self, system_prompt: str, user_message: str):
        stream = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    async def _anthropic_stream(self, system_prompt: str, user_message: str):
        stream = await anthropic_client.messages.create(
            model=LLM_MODEL,
            max_tokens=800,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            stream=True,
        )
        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text
"""

# services/session_manager.py
FILES["storyteller_ai/backend/services/session_manager.py"] = """
from typing import Dict
from uuid import uuid4

from ..engines.gm_loop import GMLoop


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self, mode: str = "group") -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "mode": mode,
            "gm_loop": GMLoop(mode),
        }
        return session_id

    def get_loop(self, session_id: str) -> GMLoop:
        return self.sessions[session_id]["gm_loop"]


session_manager = SessionManager()
"""

# services/simulation_service.py (stub)
FILES["storyteller_ai/backend/services/simulation_service.py"] = """
\"\"\"Stub simulation service for Storyteller AI.\"\"\"


def run_simulation_step(state):
    return state
"""

# services/state_engine.py (stub)
FILES["storyteller_ai/backend/services/state_engine.py"] = """
\"\"\"Stub state engine for Storyteller AI.\"\"\"


def apply_patch(state, patch):
    state.update(patch)
    return state
"""

# models/schemas.py
FILES["storyteller_ai/backend/models/schemas.py"] = """
from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class Character(BaseModel):
    name: str
    clan: Optional[str] = None
    attributes: Dict[str, Any] = {}
    conditions: List[str] = []


class Scene(BaseModel):
    location: str
    tension: str = "medium"


class GameState(BaseModel):
    scene: Scene
    characters: List[Character] = []
    campaign: Dict[str, Any] = {}
"""

# README
FILES["storyteller_ai/README.md"] = """
Storyteller AI Backend
======================
Generated by bootstrap_backend.py

Quickstart
----------
1. Create and activate a virtual environment.
2. Install dependencies (FastAPI, Uvicorn, Pydantic, OpenAI, Anthropic, etc.).
3. Run:

    uvicorn storyteller_ai.backend.main:app --reload

4. Use the /sessions and /gm endpoints to drive the GM loop.
"""

# -----------------------------
# MAIN EXECUTION
# -----------------------------
def main():
    print("Storyteller AI — Backend Bootstrap")
    print("Root:", ROOT)
    print()

    # Ensure base dirs
    for d in [
        "storyteller_ai",
        "storyteller_ai/backend",
        "storyteller_ai/backend/routers",
        "storyteller_ai/backend/gm_modes",
        "storyteller_ai/backend/engines",
        "storyteller_ai/backend/services",
        "storyteller_ai/backend/models",
    ]:
        ensure_dir(ROOT / d)

    for rel, content in FILES.items():
        write_file(rel, content)

    print("\nBootstrap complete.")
    print("Next steps:")
    print("  1) Create a virtualenv and install dependencies.")
    print("  2) Run: uvicorn storyteller_ai.backend.main:app --reload")


if __name__ == "__main__":
    main()