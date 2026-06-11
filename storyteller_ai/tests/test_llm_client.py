import asyncio

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
