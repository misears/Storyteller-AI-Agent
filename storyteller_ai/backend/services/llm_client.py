import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import uuid4

from dotenv import load_dotenv
import httpx

from .llm_response import LLMResponse
from .ai_setup import ai_setup_service
from ..models.tools import ProviderResponse, ToolCall, ToolSpec
from .llm_protocol import adapt_legacy_response
from .retry import with_retries
from .runtime_settings import runtime_settings

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

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


def _get_llm_settings() -> dict[str, str]:
    return runtime_settings.get_llm()


def _get_llm_model() -> str:
    return _get_llm_settings()["model"]


def _get_ollama_url() -> str:
    return _get_llm_settings()["ollama_url"]


def _get_ollama_model() -> str:
    return _get_llm_settings()["ollama_model"]


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, str):
        try:
            raw_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
    return raw_arguments if isinstance(raw_arguments, dict) else {}


def _openai_tool_specs(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    } for tool in tools]


def _normalize_finish_reason(value: str | None) -> str:
    return value if value in {"stop", "tool_calls", "length", "error"} else "stop"


def _ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for message in messages:
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            normalized.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": [{
                    "function": {
                        "name": call.get("function", {}).get("name", ""),
                        "arguments": _parse_tool_arguments(call.get("function", {}).get("arguments", {})),
                    },
                } for call in message["tool_calls"]],
            })
        elif role == "tool":
            normalized.append({
                "role": "tool",
                "tool_name": message.get("name", ""),
                "content": str(message.get("content", "")),
            })
        else:
            normalized.append({
                "role": role,
                "content": str(message.get("content", "")),
            })
    return normalized


def _anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_prompt = "\n\n".join(
        str(message.get("content", "")) for message in messages
        if message.get("role") == "system"
    )
    history: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "tool":
            result = {
                "type": "tool_result",
                "tool_use_id": message.get("tool_call_id", ""),
                "content": str(message.get("content", "")),
            }
            if history and history[-1]["role"] == "user" and isinstance(history[-1]["content"], list):
                history[-1]["content"].append(result)
            else:
                history.append({"role": "user", "content": [result]})
            continue
        if role == "assistant" and message.get("tool_calls"):
            blocks = []
            if message.get("content"):
                blocks.append({"type": "text", "text": str(message["content"])})
            for call in message["tool_calls"]:
                function = call.get("function", {})
                blocks.append({
                    "type": "tool_use",
                    "id": call.get("id", str(uuid4())),
                    "name": function.get("name", ""),
                    "input": _parse_tool_arguments(function.get("arguments", {})),
                })
            history.append({"role": "assistant", "content": blocks})
            continue
        if role in {"user", "assistant"}:
            history.append({"role": role, "content": str(message.get("content", ""))})
    return system_prompt, history


class BaseProvider:
    supports_native_tools = False

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        raise NotImplementedError()

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Streaming is not supported for this provider.")

    async def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
    ) -> ProviderResponse:
        system_prompt = "\n\n".join(
            str(message.get("content", "")) for message in messages
            if message.get("role") == "system"
        )
        transcript = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            if role == "tool":
                transcript.append(
                    f"Validated result from {message.get('name', 'tool')}: {message.get('content', '')}"
                )
            elif role == "assistant" and message.get("tool_calls"):
                transcript.append(f"Your proposed game actions: {message.get('content') or ''}")
            elif role in {"user", "assistant"}:
                label = "Player action" if role == "user" else "Previous response"
                transcript.append(f"{label}: {message.get('content', '')}")
        user_message = "\n\n".join(transcript)
        return adapt_legacy_response(await self.generate(system_prompt, user_message))


class LLMTimeoutError(RuntimeError):
    """Raised when an LLM request exceeds its configured generation budget."""


class OllamaConnectionError(RuntimeError):
    """Raised when the local Ollama service cannot be reached."""


class OpenAIProvider(BaseProvider):
    supports_native_tools = True

    def __init__(self):
        from openai import AsyncOpenAI

        api_key = ai_setup_service.credentials.get("openai") or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key)

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

    async def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
    ) -> ProviderResponse:
        response = await self.client.chat.completions.create(
            model=_get_llm_model(),
            messages=messages,
            tools=_openai_tool_specs(tools),
            tool_choice="auto" if tools else "none",
            temperature=0.7,
        )
        choice = response.choices[0]
        message = choice.message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=_parse_tool_arguments(call.function.arguments),
            )
            for call in (message.tool_calls or [])
        ]
        return ProviderResponse(
            text=message.content or "",
            tool_calls=calls,
            finish_reason="tool_calls" if calls else _normalize_finish_reason(choice.finish_reason),
        )

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=_get_llm_model(),
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
    supports_native_tools = True

    def __init__(self):
        import anthropic

        api_key = ai_setup_service.credentials.get("anthropic") or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

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

    async def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
    ) -> ProviderResponse:
        system_prompt, history = _anthropic_messages(messages)
        response = await self.client.messages.create(
            model=_get_llm_model(),
            max_tokens=800,
            temperature=0.7,
            system=system_prompt,
            messages=history,
            tools=[{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            } for tool in tools],
            tool_choice={"type": "auto"},
        )
        text_parts = []
        calls = []
        for block in response.content:
            if block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
            elif block.type == "text":
                text_parts.append(block.text)
        finish_reason = "tool_calls" if calls else "stop"
        if response.stop_reason == "max_tokens":
            finish_reason = "length"
        return ProviderResponse(
            text="\n".join(text_parts), tool_calls=calls, finish_reason=finish_reason,
        )

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
    supports_native_tools = True

    async def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
        response_schema: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        url = f"{_get_ollama_url().rstrip('/')}/api/chat"
        settings = _get_llm_settings()
        connect_timeout = float(settings["ollama_connect_timeout"])
        read_timeout = float(settings["ollama_read_timeout"])
        think: bool | str = settings["ollama_think"]
        if think in {"true", "false"}:
            think = think == "true"
        payload: dict[str, Any] = {
            "model": _get_ollama_model(),
            "messages": _ollama_messages(messages),
            "stream": False,
            "think": think,
            "options": {
                "temperature": 0.7,
                "num_ctx": int(settings["ollama_context_window"]),
                "num_predict": int(settings["ollama_max_output_tokens"]),
            },
        }
        if response_schema is not None:
            payload["format"] = response_schema
        elif tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        data = await self._post_json(url, payload, connect_timeout, read_timeout)
        message = data.get("message") or {}
        calls: list[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            arguments = _parse_tool_arguments(function.get("arguments") or {})
            calls.append(ToolCall(
                id=raw_call.get("id") or str(uuid4()),
                name=function.get("name") or "",
                arguments=arguments,
            ))

        text = message.get("content") or ""
        done_reason = data.get("done_reason")
        finish_reason = "tool_calls" if calls else "length" if done_reason == "length" else "stop"
        return ProviderResponse(text=text, tool_calls=calls, finish_reason=finish_reason)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        url = f"{_get_ollama_url().rstrip('/')}/v1/chat/completions"
        settings = _get_llm_settings()
        connect_timeout = float(settings["ollama_connect_timeout"])
        read_timeout = float(settings["ollama_read_timeout"])
        payload = {
            "model": _get_ollama_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 800,
        }

        data = await self._post_chat_completion(url, payload, connect_timeout, read_timeout)
        choice = data["choices"][0]
        message = choice.get("message", {})
        text = message.get("content") or choice.get("text") or ""
        return LLMResponse(text=text, metadata={})

    async def _post_chat_completion(
        self, url: str, payload: dict[str, Any], connect_timeout: float, read_timeout: float,
    ) -> dict[str, Any]:
        data = await self._post_json(url, payload, connect_timeout, read_timeout)
        if not data.get("choices"):
            raise RuntimeError("Ollama response did not contain any choices.")
        return data

    async def _post_json(
        self, url: str, payload: dict[str, Any], connect_timeout: float, read_timeout: float,
    ) -> dict[str, Any]:
        try:
            timeout = httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=connect_timeout,
                pool=connect_timeout,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Ollama did not return a response within {read_timeout:g} seconds. "
                "The model may still be loading or generating; try again or increase "
                "OLLAMA_READ_TIMEOUT and OLLAMA_TOTAL_TIMEOUT."
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaConnectionError(
                f"Unable to reach Ollama at {_get_ollama_url()}: {exc}. "
                "Check that Ollama is running and OLLAMA_URL is correct."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc

        return data


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
    provider = _get_llm_settings()["provider"].lower()
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

    @property
    def supports_native_tools(self) -> bool:
        return self.provider.supports_native_tools

    @property
    def uses_ollama(self) -> bool:
        return isinstance(self.provider, OllamaProvider)

    async def generate(self, system_prompt: str, user_message: str) -> LLMResponse:
        if not isinstance(self.provider, OllamaProvider):
            return await with_retries(self.provider.generate, system_prompt, user_message)

        settings = _get_llm_settings()
        total_timeout = float(settings["ollama_total_timeout"])
        retries = int(settings["ollama_connect_retries"])
        try:
            async with asyncio.timeout(total_timeout):
                return await with_retries(
                    self.provider.generate,
                    system_prompt,
                    user_message,
                    retries=retries,
                    retry_exceptions=(httpx.ConnectError, httpx.ConnectTimeout),
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"Unable to connect to Ollama at {_get_ollama_url()} after {retries + 1} "
                "attempt(s). Check that Ollama is running and OLLAMA_URL is correct."
            ) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(
                f"Ollama generation exceeded the {total_timeout:g}-second total time limit. "
                "The turn was not committed. Increase OLLAMA_TOTAL_TIMEOUT or retry the action."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                "Ollama timed out while connecting or generating. The turn was not committed; "
                "check the model and timeout settings, then retry the action."
            ) from exc

    async def generate_with_tools(
        self, messages: list[dict[str, Any]], tools: list[ToolSpec],
        response_schema: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        if not isinstance(self.provider, OllamaProvider):
            return await self.provider.generate_with_tools(messages, tools)

        settings = _get_llm_settings()
        total_timeout = float(settings["ollama_total_timeout"])
        retries = int(settings["ollama_connect_retries"])
        try:
            async with asyncio.timeout(total_timeout):
                return await with_retries(
                    self.provider.generate_with_tools,
                    messages,
                    tools,
                    retries=retries,
                    retry_exceptions=(httpx.ConnectError, httpx.ConnectTimeout),
                    **({"response_schema": response_schema} if response_schema is not None else {}),
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"Unable to connect to Ollama at {_get_ollama_url()} after {retries + 1} "
                "attempt(s). Check that Ollama is running and OLLAMA_URL is correct."
            ) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(
                f"Ollama tool loop exceeded the {total_timeout:g}-second total time limit. "
                "The turn was not committed. Increase OLLAMA_TOTAL_TIMEOUT or retry the action."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                "Ollama timed out while connecting or generating. The turn was not committed; "
                "check the model and timeout settings, then retry the action."
            ) from exc

    async def stream(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        return await self.provider.stream(system_prompt, user_message)
