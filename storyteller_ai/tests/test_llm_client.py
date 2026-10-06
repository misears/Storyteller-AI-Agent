import asyncio

import httpx
import pytest

from backend.services.runtime_settings import runtime_settings
from backend.services.llm_client import (
    LLMClient,
    LLMResponse,
    LLMTimeoutError,
    OllamaConnectionError,
    OllamaProvider,
)
from backend.services import llm_client
from backend.models.tools import ToolSpec


def test_mock_provider_generates_text(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    client = LLMClient()
    response = asyncio.run(client.generate("system prompt", "user action"))

    assert response.text.startswith("[Mock LLM]")
    assert isinstance(response.metadata, dict)


def test_mock_provider_state_update(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    client = LLMClient()
    response = asyncio.run(client.generate("system prompt", "please change state_update"))

    assert response.metadata.get("state_update") == {"scene": {"tension": "high"}}


def test_default_provider_prefers_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    settings = runtime_settings.get_llm()

    assert settings["provider"] == "ollama"
    assert settings["ollama_model"] == "llama2:7b"


def test_ollama_timeout_defaults_are_bounded(monkeypatch):
    monkeypatch.setattr(runtime_settings, "_overrides", {})
    for key in (
        "OLLAMA_CONNECT_TIMEOUT",
        "OLLAMA_READ_TIMEOUT",
        "OLLAMA_TOTAL_TIMEOUT",
        "OLLAMA_CONNECT_RETRIES",
        "OLLAMA_CONTEXT_WINDOW",
        "OLLAMA_MAX_OUTPUT_TOKENS",
        "OLLAMA_THINK",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = runtime_settings.get_llm()

    assert settings["ollama_connect_timeout"] == "10.0"
    assert settings["ollama_read_timeout"] == "600.0"
    assert settings["ollama_total_timeout"] == "900.0"
    assert settings["ollama_connect_retries"] == "1"
    assert settings["ollama_context_window"] == "8192"
    assert settings["ollama_max_output_tokens"] == "800"
    assert settings["ollama_think"] == "false"


def test_ollama_provider_uses_separate_connect_and_read_timeouts(monkeypatch):
    settings = {
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:4b",
        "ollama_connect_timeout": "12",
        "ollama_read_timeout": "345",
    }
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: settings)
    recorded = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "ready"}}]}

    class FakeClient:
        def __init__(self, timeout):
            recorded["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            return FakeResponse()

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(OllamaProvider().generate("system", "user"))

    assert result.text == "ready"
    assert recorded["timeout"].connect == 12
    assert recorded["timeout"].read == 345


def test_ollama_total_timeout_is_actionable_and_does_not_retry(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "provider": "ollama",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_total_timeout": "0.01",
        "ollama_connect_retries": "1",
    })

    class SlowOllama(OllamaProvider):
        calls = 0

        async def generate(self, system_prompt, user_message):
            self.calls += 1
            await asyncio.sleep(1)
            return LLMResponse(text="late")

    client = LLMClient()
    client.provider = SlowOllama()

    with pytest.raises(LLMTimeoutError, match="turn was not committed"):
        asyncio.run(client.generate("system", "user"))
    assert client.provider.calls == 1


def test_ollama_read_timeout_is_not_retried(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "provider": "ollama",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_total_timeout": "5",
        "ollama_connect_retries": "2",
    })

    class StalledOllama(OllamaProvider):
        calls = 0

        async def generate(self, system_prompt, user_message):
            self.calls += 1
            raise httpx.ReadTimeout("model did not respond")

    client = LLMClient()
    client.provider = StalledOllama()

    with pytest.raises(LLMTimeoutError, match="timed out"):
        asyncio.run(client.generate("system", "user"))
    assert client.provider.calls == 1


def test_ollama_connection_retries_are_bounded(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "provider": "ollama",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_total_timeout": "5",
        "ollama_connect_retries": "1",
    })

    class FlakyOllama(OllamaProvider):
        calls = 0

        async def generate(self, system_prompt, user_message):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("server starting")
            return LLMResponse(text="ready")

    client = LLMClient()
    client.provider = FlakyOllama()

    result = asyncio.run(client.generate("system", "user"))

    assert result.text == "ready"
    assert client.provider.calls == 2


def test_ollama_connection_retry_exhaustion_is_actionable(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "provider": "ollama",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_total_timeout": "5",
        "ollama_connect_retries": "0",
    })

    class OfflineOllama(OllamaProvider):
        async def generate(self, system_prompt, user_message):
            raise httpx.ConnectError("connection refused")

    client = LLMClient()
    client.provider = OfflineOllama()

    with pytest.raises(OllamaConnectionError, match="after 1 attempt"):
        asyncio.run(client.generate("system", "user"))


def test_ollama_tool_request_maps_registered_schemas_and_tool_calls(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:4b",
        "ollama_connect_timeout": "10",
        "ollama_read_timeout": "600",
        "ollama_context_window": "8192",
        "ollama_max_output_tokens": "800",
        "ollama_think": "false",
    })
    recorded = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"done_reason": "stop", "message": {
                "content": "Rolling now.",
                "tool_calls": [{
                    "function": {"name": "roll_dice", "arguments": {"expression": "1d10", "reason": "test"}},
                }],
            }}

    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            recorded["url"] = url
            recorded["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", FakeClient)
    tool = ToolSpec(
        name="roll_dice",
        description="Roll server-authoritative dice.",
        parameters={"type": "object", "properties": {"expression": {"type": "string"}}},
    )
    response = asyncio.run(OllamaProvider().generate_with_tools(
        [{"role": "system", "content": "rules"}, {"role": "user", "content": "roll"}],
        [tool],
    ))

    assert recorded["url"] == "http://127.0.0.1:11434/api/chat"
    assert recorded["payload"]["tools"][0]["type"] == "function"
    assert recorded["payload"]["tools"][0]["function"]["name"] == "roll_dice"
    assert recorded["payload"]["think"] is False
    assert recorded["payload"]["options"]["num_ctx"] == 8192
    assert recorded["payload"]["options"]["num_predict"] == 800
    assert response.finish_reason == "tool_calls"
    assert response.text == "Rolling now."
    assert response.tool_calls[0].name == "roll_dice"
    assert response.tool_calls[0].arguments == {"expression": "1d10", "reason": "test"}


def test_ollama_structured_response_uses_json_schema_without_tools(monkeypatch):
    from backend.models.tools import ToolSpec
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "ollama_url": "http://127.0.0.1:11434", "ollama_model": "qwen3:4b",
        "ollama_connect_timeout": "10", "ollama_read_timeout": "600",
        "ollama_context_window": "8192", "ollama_max_output_tokens": "800", "ollama_think": "false",
    })
    recorded = {}
    async def post(self, url, payload, connect_timeout, read_timeout):
        recorded.update(payload)
        return {"done_reason": "stop", "message": {"content": '{"recommendation":"approve"}'}}
    monkeypatch.setattr(OllamaProvider, "_post_json", post)
    schema = {"type": "object", "properties": {"recommendation": {"enum": ["approve", "reject"]}}}
    response = asyncio.run(OllamaProvider().generate_with_tools([], [ToolSpec(name="review", description="Review", parameters=schema)], response_schema=schema))
    assert recorded["format"] == schema
    assert "tools" not in recorded
    assert recorded["think"] is False
    assert response.text == '{"recommendation":"approve"}'


def test_ollama_malformed_tool_arguments_become_invalid_empty_object(monkeypatch):
    monkeypatch.setattr(llm_client, "_get_llm_settings", lambda: {
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:4b",
        "ollama_connect_timeout": "10",
        "ollama_read_timeout": "600",
        "ollama_context_window": "8192",
        "ollama_max_output_tokens": "800",
        "ollama_think": "false",
    })

    class FakeResponse:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {"message": {"tool_calls": [{
                "function": {"name": "apply_state_update", "arguments": "{bad json"},
            }]}}

    class FakeClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, json): return FakeResponse()

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", FakeClient)
    response = asyncio.run(OllamaProvider().generate_with_tools([], []))

    assert response.tool_calls[0].arguments == {}


def test_ollama_tool_conversation_uses_native_assistant_and_tool_messages():
    messages = llm_client._ollama_messages([
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "roll"},
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "call-1", "type": "function",
            "function": {"name": "roll_dice", "arguments": '{"expression":"1d10"}'},
        }]},
        {"role": "tool", "tool_call_id": "call-1", "name": "roll_dice", "content": '{"ok":true}'},
    ])

    assert messages[2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "function": {"name": "roll_dice", "arguments": {"expression": "1d10"}},
        }],
    }
    assert messages[3] == {
        "role": "tool", "tool_name": "roll_dice", "content": '{"ok":true}',
    }
