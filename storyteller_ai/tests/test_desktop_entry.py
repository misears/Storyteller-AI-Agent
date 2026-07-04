import desktop_entry


def test_desktop_entry_sets_log_config_none(monkeypatch):
    called = {}

    def fake_run(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(desktop_entry.uvicorn, "run", fake_run)
    monkeypatch.setenv("STORYTELLER_HOST", "127.0.0.1")
    monkeypatch.setenv("STORYTELLER_PORT", "8000")

    desktop_entry.main()

    assert called["args"][0] == "backend.main:app"
    assert called["kwargs"]["log_config"] is None
    assert called["kwargs"]["reload"] is False
