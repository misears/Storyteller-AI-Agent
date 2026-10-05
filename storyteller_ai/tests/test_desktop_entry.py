import desktop_entry
import pytest


def test_desktop_entry_sets_log_config_none(monkeypatch):
    called = {}

    def fake_run(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(desktop_entry.uvicorn, "run", fake_run)
    monkeypatch.delenv("STORYTELLER_HOST", raising=False)
    monkeypatch.setenv("STORYTELLER_PORT", "8000")

    desktop_entry.main()

    assert called["args"][0] == "backend.main:app"
    assert called["kwargs"]["host"] == "127.0.0.1"
    assert called["kwargs"]["log_config"] is None
    assert called["kwargs"]["reload"] is False


def test_desktop_entry_refuses_non_loopback_bind(monkeypatch):
    monkeypatch.setenv("STORYTELLER_HOST", "0.0.0.0")

    with pytest.raises(ValueError, match="loopback host"):
        desktop_entry.main()
