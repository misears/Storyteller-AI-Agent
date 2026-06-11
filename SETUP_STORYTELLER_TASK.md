# Storyteller AI — Project Setup Task

This task defines the full directory structure and required files for the Storyteller AI backend, including:

- GM Loop + LLM wiring
- State update extraction
- Tool-calling support
- Streaming support
- Retry logic
- Engines (factions, city, NPC memory, secrecy, chronicle starter)
- GM modes
- Services (simulation, sessions, LLM client)
- Routers (gm, sessions, tools, dashboard)
- Utilities

---

## 1. DIRECTORY STRUCTURE

Create the following structure:

```
storyteller_ai/
  backend/
    main.py
    routers/
      gm.py
      sessions.py
      tools.py
      dashboard.py
    gm_modes/
      __init__.py
      solo.py
      group.py
      assistant.py
      orchestrator.py
      prompt_wrapper.py
      scene_framing.py
    engines/
      gm_loop.py
      faction_ai.py
      faction_engine.py
      city_map.py
      npc_memory.py
      secrecy_tracker.py
      chronicle_starter.py
      turn_engine.py
      scene_predictor.py
      pc_builder.py
      combat_engine.py
      dice_pool.py
    services/
      llm_client.py
      llm_response.py
      llm_utils.py
      retry.py
      simulation_service.py
      session_manager.py
      state_engine.py
    models/
      schemas.py
  scripts/
    setup_structure.bat
  README.md
```

---

## 2. REQUIRED FILE CONTENTS

### **2.1 GM Loop (gm_loop.py)**

```python
from backend.gm_modes.orchestrator import GMOrchestrator
from backend.services.llm_client import LLMClient
from backend.services.llm_utils import extract_state_update

class GMLoop:
    def __init__(self, mode: str = "group"):
        self.mode = mode
        self.orchestrator = GMOrchestrator(mode)
        self.llm = LLMClient()

    async def step(self, user_message: str) -> dict:
        system_prompt = await self.orchestrator.build_prompt(user_message)
        response = await self.llm.generate(system_prompt=system_prompt, user_message=user_message)

        cleaned_text, state_update = extract_state_update(response.text)
        if state_update:
            self.orchestrator.apply_state_update(state_update)

        return {"text": cleaned_text, "mode": self.mode}
```

---

### **2.2 LLM Client (llm_client.py)**  
Supports:
- OpenAI
- Anthropic  
- Tool-calling  
- Streaming  
- Retry logic

```python
import os
from backend.services.llm_response import LLMResponse
from backend.services.retry import with_retries

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

        return LLMResponse(text="\n".join(text_parts), metadata=metadata)
```

---

### **2.3 State Update Extraction (llm_utils.py)**

```python
import json
import re

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

def extract_state_update(text: str):
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
```

---

### **2.4 Retry Logic (retry.py)**

```python
import asyncio

async def with_retries(func, *args, retries=3, base_delay=0.5, **kwargs):
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
```

---

### **2.5 System Prompt (GM Mode Orchestrator)**  
Place this in `gm_modes/orchestrator.py`:

```python
SYSTEM_PROTOCOL = """
[INSERT THE FULL SYSTEM PROMPT YOU GENERATED EARLIER HERE]
"""
```

---

# END OF TASK
