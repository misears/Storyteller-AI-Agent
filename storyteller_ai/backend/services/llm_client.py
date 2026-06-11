import json
import os
from typing import AsyncGenerator

import httpx

from .llm_response import LLMResponse
from .retry import with_retries

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


def _get_env_lower(name: str, default: str) -> str:
    return os.getenv(name, default).lower()


def _get_llm_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def _get_ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


def _get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", _get_llm_model())


class BaseProvider:
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        raise NotImplementedError()

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Streaming is not supported for this provider.")


class OpenAIProvider(BaseProvider):
    def __init__(self):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=_get_llm_model(),
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

        if getattr(choice, "finish_reason", None) == "tool_calls" and getattr(choice.message, "tool_calls", None):
            for tool_call in choice.message.tool_calls:
                if tool_call.function.name == "apply_state_update":
                    args = json.loads(tool_call.function.arguments)
                    metadata["state_update"] = args.get("state_update")

        text = choice.message.content or ""
        return LLMResponse(text=text, metadata=metadata)

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
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


class AnthropicProvider(BaseProvider):
    def __init__(self):
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        response = await self.client.messages.create(
            model=_get_llm_model(),
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
        stream = await self.client.messages.create(
            model=_get_llm_model(),
            max_tokens=800,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            stream=True,
        )

        async for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield event.delta.text


class OllamaProvider(BaseProvider):
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        url = f"{_get_ollama_url().rstrip('/')}/v1/chat/completions"
        payload = {
            "model": _get_ollama_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 800,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Unable to reach Ollama at {_get_ollama_url()}: {exc}. "
                "Check that the Ollama server is running and OLLAMA_URL is correct."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc

        if not data.get("choices"):
            raise RuntimeError("Ollama response did not contain any choices.")

        choice = data["choices"][0]
        message = choice.get("message", {})
        text = message.get("content") or choice.get("text") or ""
        return LLMResponse(text=text, metadata={})


class MockProvider(BaseProvider):
    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        text = (
            "[Mock LLM] The storyteller considers your action and responds with a narrative outcome."
        )
        metadata = {}
        lowered = user_message.lower()
        if "state_update" in lowered or "update" in lowered:
            metadata["state_update"] = {"scene": {"tension": "high"}}
        return LLMResponse(text=text, metadata=metadata)


def _build_provider() -> BaseProvider:
    provider = _get_env_lower("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "mock":
        return MockProvider()
    raise RuntimeError(
        f"Unsupported LLM provider: {provider}. "
        "Supported providers are openai, anthropic, ollama, and mock."
    )


class LLMClient:
    def __init__(self):
        self.provider = _build_provider()

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        return await with_retries(self.provider.generate, system_prompt, user_message)

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        return await self.provider.stream(system_prompt, user_message)
