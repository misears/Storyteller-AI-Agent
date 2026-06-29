import os
import threading
import time
import webbrowser

from .app_paths import is_frozen


def _should_launch_browser() -> bool:
    if os.getenv("STORYTELLER_SKIP_BROWSER", "0").strip() == "1":
        return False
    return is_frozen() or os.getenv("STORYTELLER_OPEN_BROWSER", "0").strip() == "1"


def launch_browser_when_ready(url: str = "http://127.0.0.1:8000/") -> threading.Thread | None:
    if not _should_launch_browser():
        return None

    def _open() -> None:
        for _ in range(60):
            try:
                if webbrowser.open(url, new=1, autoraise=True):
                    return
            except Exception:
                pass
            time.sleep(0.5)

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()
    return thread