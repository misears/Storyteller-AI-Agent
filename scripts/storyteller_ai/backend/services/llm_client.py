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

        return LLMResponse(text="\n".join(text_parts), metadata=metadata)

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
