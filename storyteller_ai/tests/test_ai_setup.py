import asyncio
import sys

import pytest

from backend.services.ai_setup import AIConfigStore, AISetupService, OllamaRuntimeManager, WindowsCredentialStore


def test_ai_config_persists_only_nonsecret_preferences(tmp_path):
    store = AIConfigStore(tmp_path / "ai-settings.json")

    saved = store.save({"provider": "ollama", "model": "qwen3:4b-instruct", "ollama_mode": "cpu"})
    loaded = AIConfigStore(store.path).load()

    assert loaded == saved
    assert loaded["provider"] == "ollama"
    assert loaded["model"] == "qwen3:4b-instruct"
    assert loaded["ollama_mode"] == "cpu"
    assert "api_key" not in store.path.read_text(encoding="utf-8").lower()


def test_ai_config_rejects_invalid_provider_mode_and_model(tmp_path):
    store = AIConfigStore(tmp_path / "ai-settings.json")
    with pytest.raises(ValueError, match="provider"):
        store.save({"provider": "shell", "model": "qwen3:4b", "ollama_mode": "auto"})
    with pytest.raises(ValueError, match="ollama_mode"):
        store.save({"provider": "ollama", "model": "qwen3:4b", "ollama_mode": "gpu"})
    with pytest.raises(ValueError, match="model"):
        store.save({"provider": "ollama", "model": "", "ollama_mode": "auto"})


def test_ai_config_defaults_to_the_active_provider_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.ai_setup.runtime_settings.get_llm",
        lambda: {"provider": "openai", "model": "gpt-4o-mini", "ollama_model": "qwen3:4b-instruct"},
    )

    config = AIConfigStore(tmp_path / "ai-settings.json").load()

    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o-mini"


def test_initialize_reconciles_missing_legacy_model_to_installed_default(tmp_path, monkeypatch):
    service = AISetupService()
    service.config = AIConfigStore(tmp_path / "ai-settings.json")
    service.config.save({"provider": "ollama", "model": "llama2:7b", "ollama_mode": "auto"})
    monkeypatch.setattr(service.ollama, "start", lambda _mode: asyncio.sleep(0))
    monkeypatch.setattr(
        service.ollama,
        "status",
        lambda mode: asyncio.sleep(0, result={"models": [{"name": "qwen3:4b-instruct"}, {"name": "gemma4:26b"}]}),
    )
    monkeypatch.setattr("backend.services.ai_setup.runtime_settings.update_llm", lambda _settings: None)

    asyncio.run(service.initialize())

    assert service.config.load()["model"] == "qwen3:4b-instruct"


def test_credential_store_protects_and_deletes_provider_key(tmp_path, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows DPAPI is required for credential encryption")
    monkeypatch.setattr(WindowsCredentialStore, "_protect", staticmethod(lambda value: b"encrypted:" + value[::-1]))
    monkeypatch.setattr(WindowsCredentialStore, "_unprotect", staticmethod(lambda value: value.removeprefix(b"encrypted:")[::-1]))
    store = WindowsCredentialStore(tmp_path / "credentials")
    api_key = "test-secret-key-do-not-persist-plaintext"

    store.set("openai", api_key)
    encrypted_file = tmp_path / "credentials" / "openai.dpapi"

    assert store.has("openai")
    assert api_key.encode() not in encrypted_file.read_bytes()
    assert store.get("openai") == api_key
    store.delete("openai")
    assert store.has("openai") is False
    assert store.get("openai") is None


def test_auto_mode_reuses_existing_ollama_without_owning_or_stopping_it(monkeypatch):
    manager = OllamaRuntimeManager()
    monkeypatch.setattr(manager, "_healthy", lambda url: asyncio.sleep(0, result=url.endswith(":11434")))
    monkeypatch.setattr(manager, "_find_executable", lambda: pytest.fail("must not start a child"))

    result = asyncio.run(manager.start("auto"))

    assert result == {"url": "http://127.0.0.1:11434", "managed": False, "mode": "auto"}
    assert manager._process is None


def test_cpu_mode_launches_an_owned_process_with_gpu_backends_disabled(monkeypatch, tmp_path):
    manager = OllamaRuntimeManager()
    monkeypatch.setattr(manager, "_find_executable", lambda: "ollama.exe")
    monkeypatch.setattr(manager, "_free_port", lambda: 42135)
    calls = []

    async def healthy(url):
        return url.endswith(":42135")

    class FakeProcess:
        def poll(self):
            return None
        def terminate(self):
            calls.append("terminate")
        def wait(self, timeout=None):
            calls.append("wait")
            return 0
        def kill(self):
            calls.append("kill")

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(manager, "_healthy", healthy)
    monkeypatch.setattr("backend.services.ai_setup.subprocess.Popen", fake_popen)

    result = asyncio.run(manager.start("cpu"))
    command, process_options = calls[0]

    assert result == {"url": "http://127.0.0.1:42135", "managed": True, "mode": "cpu"}
    assert command == ["ollama.exe", "serve"]
    assert process_options["env"]["OLLAMA_HOST"] == "127.0.0.1:42135"
    assert process_options["env"]["CUDA_VISIBLE_DEVICES"] == "-1"
    assert process_options["env"]["OLLAMA_VULKAN"] == "0"
    assert process_options["stdout"] == process_options["stderr"]
    asyncio.run(manager.stop())
    assert calls[-2:] == ["terminate", "wait"]


def test_cpu_mode_uses_a_fresh_port_even_if_another_service_is_running(monkeypatch):
    manager = OllamaRuntimeManager()
    monkeypatch.setattr(manager, "_find_executable", lambda: "ollama.exe")
    monkeypatch.setattr(manager, "_free_port", lambda: 42136)
    healthy_urls = []

    async def healthy(url):
        healthy_urls.append(url)
        return True

    class FakeProcess:
        def poll(self):
            return None

    monkeypatch.setattr(manager, "_healthy", healthy)
    monkeypatch.setattr("backend.services.ai_setup.subprocess.Popen", lambda *_args, **_kwargs: FakeProcess())

    result = asyncio.run(manager.start("cpu"))

    assert result["url"] == "http://127.0.0.1:42136"
    assert "http://127.0.0.1:11435" not in healthy_urls


def test_model_pull_names_are_validated_before_background_start():
    manager = OllamaRuntimeManager()

    with pytest.raises(ValueError, match="unsupported characters"):
        manager.start_pull("../../run-command")

    with pytest.raises(ValueError, match="unsupported characters"):
        manager.start_pull("model name with spaces")


def test_model_pull_records_progress_and_completes(monkeypatch):
    manager = OllamaRuntimeManager()
    manager._jobs["job-1"] = {"id": "job-1", "model": "fixture:1b", "status": "queued", "completed": 0, "total": None, "error": None}
    monkeypatch.setattr("backend.services.ai_setup.runtime_settings.get_llm", lambda: {"ollama_url": "http://ollama.test"})

    class FakeResponse:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            yield '{"status":"downloading","completed":50,"total":100}'
            yield '{"status":"verifying","completed":100,"total":100}'

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *_args):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeStream()

    monkeypatch.setattr("backend.services.ai_setup.httpx.AsyncClient", FakeClient)

    asyncio.run(manager._pull("job-1", "fixture:1b"))

    status = manager.pull_status("job-1")
    assert status["status"] == "complete"
    assert status["progress"] == "Model ready"
    assert status["completed"] == 100
    assert status["total"] == 100


def test_model_pull_failure_returns_actionable_redacted_error(monkeypatch):
    manager = OllamaRuntimeManager()
    manager._jobs["job-2"] = {"id": "job-2", "model": "fixture:missing", "status": "queued", "completed": 0, "total": None, "error": None}
    monkeypatch.setattr("backend.services.ai_setup.runtime_settings.get_llm", lambda: {"ollama_url": "http://ollama.test"})

    class FakeResponse:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            yield '{"error":"private upstream detail"}'

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *_args):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeStream()

    monkeypatch.setattr("backend.services.ai_setup.httpx.AsyncClient", FakeClient)

    asyncio.run(manager._pull("job-2", "fixture:missing"))

    status = manager.pull_status("job-2")
    assert status["status"] == "failed"
    assert status["error"] == "Model download failed. Check Ollama's status and try again."
    assert "private upstream detail" not in str(status)


def test_model_pull_can_be_cancelled_and_reports_terminal_status(monkeypatch):
    manager = OllamaRuntimeManager()
    manager._jobs["job-3"] = {"id": "job-3", "model": "fixture:1b", "status": "queued", "completed": 0, "total": None, "error": None}
    monkeypatch.setattr("backend.services.ai_setup.runtime_settings.get_llm", lambda: {"ollama_url": "http://ollama.test"})
    stream_started = asyncio.Event()

    class FakeResponse:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            stream_started.set()
            await asyncio.Event().wait()
            yield "{}"

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *_args):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeStream()

    monkeypatch.setattr("backend.services.ai_setup.httpx.AsyncClient", FakeClient)

    async def run_cancel():
        task = asyncio.create_task(manager._pull("job-3", "fixture:1b"))
        manager._job_tasks["job-3"] = task
        await stream_started.wait()
        assert manager.cancel_pull("job-3") is True
        await task

    asyncio.run(run_cancel())

    status = manager.pull_status("job-3")
    assert status["status"] == "cancelled"
    assert status["progress"] == "Download cancelled"


def test_ai_preferences_survive_service_restart_without_starting_ollama(tmp_path, monkeypatch):
    config_path = tmp_path / "ai-settings.json"
    AIConfigStore(config_path).save({"provider": "anthropic", "model": "claude-test", "ollama_mode": "cpu"})
    restarted = AISetupService()
    restarted.config = AIConfigStore(config_path)
    monkeypatch.setattr(restarted.ollama, "start", lambda _mode: pytest.fail("cloud startup must not start Ollama"))
    monkeypatch.setattr("backend.services.ai_setup.runtime_settings.update_llm", lambda _settings: None)

    asyncio.run(restarted.initialize())

    assert restarted.get_config() == {"provider": "anthropic", "model": "claude-test", "ollama_mode": "cpu"}


def test_windows_dpapi_credential_store_round_trip(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows DPAPI is required for credential encryption")
    store = WindowsCredentialStore(tmp_path / "credentials")
    api_key = "sk-live-test-never-store-plaintext"

    store.set("openai", api_key)

    encrypted_file = tmp_path / "credentials" / "openai.dpapi"
    assert api_key.encode() not in encrypted_file.read_bytes()
    assert store.get("openai") == api_key
    store.delete("openai")
    assert store.get("openai") is None


def test_dpapi_key_file_contains_ciphertext_not_raw_value(tmp_path, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows DPAPI is required for credential encryption")
    monkeypatch.setattr(WindowsCredentialStore, "_protect", staticmethod(lambda value: b"protected" + value[::-1]))
    store = WindowsCredentialStore(tmp_path / "credentials")
    key = "sk-test-do-not-write-plaintext"

    store.set("anthropic", key)

    stored = (tmp_path / "credentials" / "anthropic.dpapi").read_bytes()
    assert key.encode() not in stored
    monkeypatch.setattr(WindowsCredentialStore, "_unprotect", staticmethod(lambda value: value.removeprefix(b"protected")[::-1]))
    assert store.get("anthropic") == key
