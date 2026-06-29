import asyncio

from backend.services.runtime_settings import runtime_settings
from backend.services.llm_client import LLMClient


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
