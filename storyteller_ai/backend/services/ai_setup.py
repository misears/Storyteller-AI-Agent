import asyncio
import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from .runtime_settings import runtime_settings


class AISetupError(RuntimeError):
    pass


def get_ai_config_dir() -> Path:
    override = os.getenv("STORYTELLER_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = os.getenv("LOCALAPPDATA", "").strip()
        if root:
            return Path(root) / "StorytellerAI"
    return Path.home() / ".config" / "storyteller-ai"


class AIConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or get_ai_config_dir() / "ai-settings.json"

    def load(self) -> dict[str, str]:
        defaults = runtime_settings.get_llm()
        config = {
            "provider": defaults["provider"] if defaults["provider"] in {"ollama", "openai", "anthropic"} else "ollama",
            "model": defaults["model"] or defaults["ollama_model"] or "qwen3:4b-instruct",
            "ollama_mode": "auto",
        }
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return config
        if not isinstance(stored, dict):
            return config
        if stored.get("provider") in {"ollama", "openai", "anthropic"}:
            config["provider"] = stored["provider"]
        if isinstance(stored.get("model"), str) and stored["model"].strip():
            config["model"] = stored["model"].strip()
        if stored.get("ollama_mode") in {"auto", "cpu"}:
            config["ollama_mode"] = stored["ollama_mode"]
        return config

    def save(self, updates: dict[str, str]) -> dict[str, str]:
        config = self.load()
        provider = updates.get("provider", config["provider"])
        model = updates.get("model", config["model"]).strip()
        mode = updates.get("ollama_mode", config["ollama_mode"])
        if provider not in {"ollama", "openai", "anthropic"}:
            raise ValueError("provider must be ollama, openai, or anthropic")
        if not model or len(model) > 160:
            raise ValueError("model is required and must be 160 characters or fewer")
        if mode not in {"auto", "cpu"}:
            raise ValueError("ollama_mode must be auto or cpu")
        config = {"provider": provider, "model": model, "ollama_mode": mode}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        return config


class WindowsCredentialStore:
    _PROVIDERS = {"openai", "anthropic"}

    def __init__(self, directory: Path | None = None):
        self.directory = directory or get_ai_config_dir() / "credentials"

    @staticmethod
    def _protect(secret: bytes) -> bytes:
        if sys.platform != "win32":
            raise AISetupError("Secure provider credentials are available only on Windows.")
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.POINTER(DataBlob),
            wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        source_buffer = ctypes.create_string_buffer(secret, len(secret))
        source = DataBlob(len(secret), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
        encrypted = DataBlob()
        if not crypt32.CryptProtectData(
            ctypes.byref(source), "Storyteller AI provider key", None, None, None, 1,
            ctypes.byref(encrypted),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(encrypted.pbData, encrypted.cbData)
        finally:
            kernel32.LocalFree(encrypted.pbData)

    @staticmethod
    def _unprotect(ciphertext: bytes) -> bytes:
        if sys.platform != "win32":
            raise AISetupError("Secure provider credentials are available only on Windows.")
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DataBlob),
            wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        source_buffer = ctypes.create_string_buffer(ciphertext, len(ciphertext))
        source = DataBlob(len(ciphertext), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
        decrypted = DataBlob()
        description = wintypes.LPWSTR()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(source), ctypes.byref(description), None, None, None, 1,
            ctypes.byref(decrypted),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(decrypted.pbData, decrypted.cbData)
        finally:
            kernel32.LocalFree(decrypted.pbData)
            if description:
                kernel32.LocalFree(description)

    def _path(self, provider: str) -> Path:
        if provider not in self._PROVIDERS:
            raise ValueError("unsupported cloud provider")
        return self.directory / f"{provider}.dpapi"

    def set(self, provider: str, api_key: str) -> None:
        api_key = api_key.strip()
        if not api_key or len(api_key) > 4096:
            raise ValueError("API key is required and must be 4096 characters or fewer")
        path = self._path(provider)
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self._protect(api_key.encode("utf-8"))
        fd, temporary_name = tempfile.mkstemp(prefix="credential-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encrypted)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def get(self, provider: str) -> str | None:
        path = self._path(provider)
        try:
            encrypted = path.read_bytes()
        except FileNotFoundError:
            return None
        return self._unprotect(encrypted).decode("utf-8")

    def has(self, provider: str) -> bool:
        return self._path(provider).is_file()

    def delete(self, provider: str) -> None:
        try:
            self._path(provider).unlink()
        except FileNotFoundError:
            pass


class OllamaRuntimeManager:
    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._managed_url: str | None = None
        self._managed_mode: str | None = None
        self._jobs: dict[str, dict[str, Any]] = {}
        self._job_tasks: dict[str, asyncio.Task] = {}

    @staticmethod
    def _find_executable() -> str | None:
        configured = os.getenv("OLLAMA_EXECUTABLE", "").strip()
        if configured and Path(configured).is_file():
            return configured
        found = shutil.which("ollama.exe") or shutil.which("ollama")
        if found:
            return found
        local = os.getenv("LOCALAPPDATA", "")
        if local:
            candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
            if candidate.is_file():
                return str(candidate)
        return None

    @staticmethod
    async def _healthy(url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
                response = await client.get(f"{url.rstrip('/')}/api/tags")
                return response.is_success
        except httpx.RequestError:
            return False

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    async def start(self, mode: str) -> dict[str, Any]:
        if mode not in {"auto", "cpu"}:
            raise ValueError("Ollama mode must be auto or cpu")
        if self._process and self._process.poll() is None and self._managed_mode == mode:
            if await self._healthy(self._managed_url or ""):
                runtime_settings.update_llm({"ollama_url": self._managed_url})
                return {"url": self._managed_url, "managed": True, "mode": mode}
        await self.stop()
        if mode == "auto" and await self._healthy("http://127.0.0.1:11434"):
            runtime_settings.update_llm({"ollama_url": "http://127.0.0.1:11434"})
            return {"url": "http://127.0.0.1:11434", "managed": False, "mode": "auto"}
        executable = self._find_executable()
        if executable is None:
            raise AISetupError("Ollama is not installed. Install it from the AI setup panel, then retry.")

        port = 11434 if mode == "auto" else self._free_port()
        url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["OLLAMA_HOST"] = f"127.0.0.1:{port}"
        if mode == "cpu":
            environment["CUDA_VISIBLE_DEVICES"] = "-1"
            environment["OLLAMA_VULKAN"] = "0"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            [executable, "serve"],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=(os.name != "nt"),
        )
        self._managed_url = url
        self._managed_mode = mode
        deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < deadline:
            if self._process.poll() is not None:
                self._process = None
                self._managed_url = None
                raise AISetupError("Storyteller's Ollama process stopped during startup. Try again or use Repair AI Setup.")
            if await self._healthy(url):
                runtime_settings.update_llm({"ollama_url": url})
                return {"url": url, "managed": True, "mode": mode}
            await asyncio.sleep(0.25)
        await self.stop()
        raise AISetupError("Ollama did not become ready within 60 seconds. Check installation and try again.")

    async def stop(self) -> None:
        process = self._process
        self._process = None
        self._managed_url = None
        self._managed_mode = None
        if process and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, 5)

    async def status(self, mode: str) -> dict[str, Any]:
        default_url = "http://127.0.0.1:11434"
        url = self._managed_url or ("http://127.0.0.1:11435" if mode == "cpu" else default_url)
        running = await self._healthy(url)
        models: list[dict[str, Any]] = []
        if running:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{url}/api/tags")
                    response.raise_for_status()
                    models = response.json().get("models", [])
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
                models = []
        return {
            "running": running,
            "url": url if running else None,
            "managed": bool(self._process and self._process.poll() is None),
            "mode": mode,
            "models": [{"name": item.get("name"), "size": item.get("size")} for item in models],
        }

    def start_pull(self, model: str) -> dict[str, str]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", model):
            raise ValueError("Model name contains unsupported characters")
        job_id = os.urandom(16).hex()
        self._jobs[job_id] = {"id": job_id, "model": model, "status": "queued", "completed": 0, "total": None, "error": None}
        task = asyncio.create_task(self._pull(job_id, model))
        self._job_tasks[job_id] = task
        task.add_done_callback(lambda _: self._job_tasks.pop(job_id, None))
        return {"id": job_id, "status": "queued"}

    async def _pull(self, job_id: str, model: str) -> None:
        job = self._jobs[job_id]
        job["status"] = "pulling"
        url = runtime_settings.get_llm()["ollama_url"].rstrip("/")
        try:
            timeout = httpx.Timeout(connect=10, read=120, write=10, pool=10)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{url}/api/pull", json={"name": model, "stream": True}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        message = json.loads(line)
                        if message.get("error"):
                            raise AISetupError("Ollama could not download this model. Check the model name and connection, then retry.")
                        job["progress"] = message.get("status", "Downloading model")
                        job["completed"] = message.get("completed", job["completed"])
                        job["total"] = message.get("total", job["total"])
            job["status"] = "complete"
            job["progress"] = "Model ready"
        except asyncio.CancelledError:
            job["status"] = "cancelled"
            job["progress"] = "Download cancelled"
        except Exception:
            job["status"] = "failed"
            job["progress"] = "Download failed"
            job["error"] = "Model download failed. Check Ollama's status and try again."

    def pull_status(self, job_id: str) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError("Model download not found")
        return dict(job)

    def cancel_pull(self, job_id: str) -> bool:
        task = self._job_tasks.get(job_id)
        if not task or task.done():
            return False
        task.cancel()
        return True

    async def shutdown(self) -> None:
        for task in tuple(self._job_tasks.values()):
            task.cancel()
        if self._job_tasks:
            await asyncio.gather(*tuple(self._job_tasks.values()), return_exceptions=True)
        await self.stop()


class AISetupService:
    def __init__(self):
        self.config = AIConfigStore()
        self.credentials = WindowsCredentialStore()
        self.ollama = OllamaRuntimeManager()

    def get_config(self) -> dict[str, str]:
        return self.config.load()

    def _apply_runtime(self, config: dict[str, str]) -> None:
        provider = config["provider"]
        runtime_settings.update_llm({
            "provider": provider,
            "model": config["model"],
            "ollama_model": config["model"] if provider == "ollama" else runtime_settings.get_llm()["ollama_model"],
        })

    async def configure(self, updates: dict[str, str]) -> dict[str, Any]:
        config = self.config.save(updates)
        self._apply_runtime(config)
        if config["provider"] == "ollama":
            await self.ollama.start(config["ollama_mode"])
        else:
            await self.ollama.stop()
        return await self.status()

    async def initialize(self) -> None:
        config = self.config.load()
        self._apply_runtime(config)
        if config["provider"] == "ollama":
            try:
                await self.ollama.start(config["ollama_mode"])
            except AISetupError:
                return
            status = await self.ollama.status(config["ollama_mode"])
            installed = [item["name"] for item in status["models"] if item.get("name")]
            if installed and config["model"] not in installed:
                config["model"] = "qwen3:4b-instruct" if "qwen3:4b-instruct" in installed else installed[0]
                self.config.save(config)
                self._apply_runtime(config)

    async def status(self) -> dict[str, Any]:
        config = self.config.load()
        local = await self.ollama.status(config["ollama_mode"])
        return {
            **config,
            **local,
            "credentials": {
                "openai": self.credentials.has("openai"),
                "anthropic": self.credentials.has("anthropic"),
            },
        }

    async def ensure_local(self) -> None:
        config = self.config.load()
        if config["provider"] != "ollama":
            raise ValueError("Select local Ollama before managing local models")
        await self.ollama.start(config["ollama_mode"])


ai_setup_service = AISetupService()
