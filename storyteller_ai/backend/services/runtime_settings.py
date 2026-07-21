import os
from threading import Lock
from typing import Dict


class RuntimeSettings:
    def __init__(self) -> None:
        self._lock = Lock()
        self._overrides: Dict[str, str] = {}

    def get_llm(self) -> Dict[str, str]:
        defaults = {
            "provider": os.getenv("LLM_PROVIDER", "ollama").strip().lower(),
            "model": os.getenv("LLM_MODEL", "llama2:7b").strip(),
            "ollama_url": os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip(),
            "ollama_model": os.getenv("OLLAMA_MODEL", "llama2:7b").strip(),
        }

        with self._lock:
            settings = {**defaults, **self._overrides}

        if not settings["ollama_model"]:
            settings["ollama_model"] = settings["model"]

        return settings

    def update_llm(self, updates: Dict[str, str]) -> Dict[str, str]:
        with self._lock:
            for key, value in updates.items():
                if value is None:
                    continue
                self._overrides[key] = value.strip()

        return self.get_llm()


runtime_settings = RuntimeSettings()
