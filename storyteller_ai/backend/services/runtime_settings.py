import os
from threading import Lock
from typing import Any, Dict


class RuntimeSettings:
    def __init__(self) -> None:
        self._lock = Lock()
        self._overrides: Dict[str, str] = {}
        self._profiles: Dict[str, Dict[str, Any]] = {}

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

    def get_profiles(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {role: dict(profile) for role, profile in self._profiles.items()}

    def update_profile(self, role: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        if not role.strip():
            raise ValueError("profile role is required")
        allowed = {"provider", "model", "context_window", "max_output_tokens", "supports_tools", "supports_json_schema"}
        unknown = set(profile) - allowed
        if unknown:
            raise ValueError(f"unsupported profile fields: {', '.join(sorted(unknown))}")
        with self._lock:
            self._profiles[role] = {**self._profiles.get(role, {}), **profile}
            return dict(self._profiles[role])


runtime_settings = RuntimeSettings()
