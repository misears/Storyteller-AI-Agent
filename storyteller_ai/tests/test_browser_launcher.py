import importlib


def test_browser_launcher_skips_in_dev(monkeypatch):
    monkeypatch.delenv("STORYTELLER_OPEN_BROWSER", raising=False)
    monkeypatch.delenv("STORYTELLER_SKIP_BROWSER", raising=False)

    browser_launcher = importlib.import_module("backend.services.browser_launcher")

    monkeypatch.setattr(browser_launcher, "is_frozen", lambda: False)

    called = []
    monkeypatch.setattr(browser_launcher.webbrowser, "open", lambda *args, **kwargs: called.append(True))

    thread = browser_launcher.launch_browser_when_ready("http://127.0.0.1:8000/")

    assert thread is None
    assert called == []


def test_browser_launcher_enabled_when_requested(monkeypatch):
    monkeypatch.setenv("STORYTELLER_OPEN_BROWSER", "1")
    monkeypatch.delenv("STORYTELLER_SKIP_BROWSER", raising=False)

    browser_launcher = importlib.import_module("backend.services.browser_launcher")

    monkeypatch.setattr(browser_launcher, "is_frozen", lambda: False)

    calls = []
    monkeypatch.setattr(browser_launcher.webbrowser, "open", lambda *args, **kwargs: calls.append(args[0]) or True)

    thread = browser_launcher.launch_browser_when_ready("http://127.0.0.1:8000/")
    assert thread is not None
    thread.join(timeout=1)

    assert calls == ["http://127.0.0.1:8000/"]