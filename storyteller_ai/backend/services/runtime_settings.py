import os
import math
from threading import Lock
from typing import Any, Dict


_OLLAMA_TIMEOUT_LIMITS = {
    "ollama_connect_timeout": (1.0, 120.0),
    "ollama_read_timeout": (1.0, 1800.0),
    "ollama_total_timeout": (1.0, 3600.0),
}
_OLLAMA_CONNECT_RETRY_LIMIT = 3
_OLLAMA_NUMERIC_LIMITS = {
    "ollama_context_window": (1024, 131072, 8192),
    "ollama_max_output_tokens": (64, 8192, 800),
}
_OLLAMA_THINK_VALUES = {"false", "true", "low", "medium", "high"}


def _timeout_setting(name: str, environment_name: str, default: float) -> str:
    try:
        value = float(os.getenv(environment_name, str(default)).strip())
    except ValueError:
        return str(default)
    minimum, maximum = _OLLAMA_TIMEOUT_LIMITS[name]
    if not math.isfinite(value) or not minimum <= value <= maximum:
        return str(default)
    return str(value)


def _connect_retries_setting() -> str:
    try:
        value = int(os.getenv("OLLAMA_CONNECT_RETRIES", "1").strip())
    except ValueError:
        return "1"
    if not 0 <= value <= _OLLAMA_CONNECT_RETRY_LIMIT:
        return "1"
    return str(value)


def _ollama_numeric_setting(name: str, environment_name: str) -> str:
    minimum, maximum, default = _OLLAMA_NUMERIC_LIMITS[name]
    try:
        value = int(os.getenv(environment_name, str(default)).strip())
    except ValueError:
        return str(default)
    if not minimum <= value <= maximum:
        return str(default)
    return str(value)


def _ollama_think_setting() -> str:
    value = os.getenv("OLLAMA_THINK", "false").strip().lower()
    return value if value in _OLLAMA_THINK_VALUES else "false"


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
            "ollama_connect_timeout": _timeout_setting("ollama_connect_timeout", "OLLAMA_CONNECT_TIMEOUT", 10.0),
            "ollama_read_timeout": _timeout_setting("ollama_read_timeout", "OLLAMA_READ_TIMEOUT", 600.0),
            "ollama_total_timeout": _timeout_setting("ollama_total_timeout", "OLLAMA_TOTAL_TIMEOUT", 900.0),
            "ollama_connect_retries": _connect_retries_setting(),
            "ollama_context_window": _ollama_numeric_setting("ollama_context_window", "OLLAMA_CONTEXT_WINDOW"),
            "ollama_max_output_tokens": _ollama_numeric_setting("ollama_max_output_tokens", "OLLAMA_MAX_OUTPUT_TOKENS"),
            "ollama_think": _ollama_think_setting(),
        }

        with self._lock:
            settings = {**defaults, **self._overrides}

        if not settings["ollama_model"]:
            settings["ollama_model"] = settings["model"]

        return settings

    def update_llm(self, updates: Dict[str, Any]) -> Dict[str, str]:
        normalized = {}
        for key, value in updates.items():
            if value is None:
                continue
            string_value = str(value).strip()
            if key in _OLLAMA_TIMEOUT_LIMITS:
                try:
                    numeric_value = float(string_value)
                except ValueError as exc:
                    raise ValueError(f"{key} must be a number") from exc
                minimum, maximum = _OLLAMA_TIMEOUT_LIMITS[key]
                if not math.isfinite(numeric_value) or not minimum <= numeric_value <= maximum:
                    raise ValueError(f"{key} must be between {minimum:g} and {maximum:g} seconds")
                string_value = str(numeric_value)
            elif key == "ollama_connect_retries":
                try:
                    retry_count = int(string_value)
                except ValueError as exc:
                    raise ValueError("ollama_connect_retries must be an integer") from exc
                if not 0 <= retry_count <= _OLLAMA_CONNECT_RETRY_LIMIT:
                    raise ValueError(
                        f"ollama_connect_retries must be between 0 and {_OLLAMA_CONNECT_RETRY_LIMIT}"
                    )
                string_value = str(retry_count)
            elif key in _OLLAMA_NUMERIC_LIMITS:
                minimum, maximum, _ = _OLLAMA_NUMERIC_LIMITS[key]
                try:
                    numeric_value = int(string_value)
                except ValueError as exc:
                    raise ValueError(f"{key} must be an integer") from exc
                if not minimum <= numeric_value <= maximum:
                    raise ValueError(f"{key} must be between {minimum} and {maximum}")
                string_value = str(numeric_value)
            elif key == "ollama_think":
                string_value = string_value.lower()
                if string_value not in _OLLAMA_THINK_VALUES:
                    raise ValueError("ollama_think must be false, true, low, medium, or high")
            normalized[key] = string_value
        with self._lock:
            self._overrides.update(normalized)

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
