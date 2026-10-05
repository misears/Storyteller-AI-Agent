from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.pdf_ingest import get_ocr_runtime_status
from ..services.ai_setup import AISetupError, ai_setup_service
from ..services.llm_client import LLMClient, LLMTimeoutError, OllamaConnectionError
from ..services.runtime_settings import runtime_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMSettingsResponse(BaseModel):
    provider: str
    model: str
    ollama_url: str
    ollama_model: str
    ollama_connect_timeout: float
    ollama_read_timeout: float
    ollama_total_timeout: float
    ollama_connect_retries: int
    ollama_context_window: int
    ollama_max_output_tokens: int
    ollama_think: str


class LLMSettingsUpdateRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_connect_timeout: Optional[float] = None
    ollama_read_timeout: Optional[float] = None
    ollama_total_timeout: Optional[float] = None
    ollama_connect_retries: Optional[int] = None
    ollama_context_window: Optional[int] = None
    ollama_max_output_tokens: Optional[int] = None
    ollama_think: Optional[str] = None


class OCRStatusResponse(BaseModel):
    active: bool
    detail: str


class ModelProfileRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_tools: Optional[bool] = None
    supports_json_schema: Optional[bool] = None


class AISetupUpdateRequest(BaseModel):
    provider: Optional[Literal["ollama", "openai", "anthropic"]] = None
    model: Optional[str] = None
    ollama_mode: Optional[Literal["auto", "cpu"]] = None


class AISecretRequest(BaseModel):
    api_key: str


class ModelPullRequest(BaseModel):
    model: str


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    return runtime_settings.get_llm()


@router.put("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    updates = payload.model_dump(exclude_none=True)
    if "provider" in updates:
        updates["provider"] = updates["provider"].lower()
    try:
        return runtime_settings.update_llm(updates)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ai")
async def get_ai_setup():
    return await ai_setup_service.status()


@router.put("/ai")
async def update_ai_setup(payload: AISetupUpdateRequest):
    try:
        return await ai_setup_service.configure(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AISetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ai/start")
async def start_local_ai():
    try:
        config = ai_setup_service.get_config()
        if config["provider"] != "ollama":
            raise HTTPException(status_code=409, detail="Select Ollama before starting a local model.")
        return await ai_setup_service.ollama.start(config["ollama_mode"])
    except AISetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ai/stop")
async def stop_local_ai():
    await ai_setup_service.ollama.stop()
    return await ai_setup_service.status()


@router.post("/ai/models/pull")
async def pull_local_model(payload: ModelPullRequest):
    try:
        await ai_setup_service.ensure_local()
        return ai_setup_service.ollama.start_pull(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AISetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ai/models/pull/{job_id}")
def get_model_pull(job_id: str):
    try:
        return ai_setup_service.ollama.pull_status(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/ai/models/pull/{job_id}")
def cancel_model_pull(job_id: str):
    try:
        cancelled = ai_setup_service.ollama.cancel_pull(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"cancelled": cancelled}


@router.put("/ai/credentials/{provider}")
def save_ai_credential(provider: str, payload: AISecretRequest):
    if provider not in {"openai", "anthropic"}:
        raise HTTPException(status_code=404, detail="Unsupported cloud provider.")
    try:
        ai_setup_service.credentials.set(provider, payload.api_key)
    except AISetupError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"provider": provider, "configured": True}


@router.delete("/ai/credentials/{provider}")
def delete_ai_credential(provider: str):
    if provider not in {"openai", "anthropic"}:
        raise HTTPException(status_code=404, detail="Unsupported cloud provider.")
    try:
        ai_setup_service.credentials.delete(provider)
    except AISetupError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"provider": provider, "configured": False}


@router.post("/ai/test")
async def test_ai_provider():
    config = ai_setup_service.get_config()
    provider = config["provider"]
    if provider in {"openai", "anthropic"} and not ai_setup_service.credentials.has(provider):
        raise HTTPException(status_code=422, detail=f"Enter the {provider} API key before testing this provider.")
    try:
        if provider == "ollama":
            await ai_setup_service.ensure_local()
        await LLMClient().generate(
            "Reply with a short readiness confirmation.",
            "Confirm you are ready.",
        )
    except (LLMTimeoutError, OllamaConnectionError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Provider test failed ({type(exc).__name__}). Check the provider and model settings.",
        ) from exc
    return {"ok": True, "provider": provider, "model": config["model"]}


@router.get("/ocr", response_model=OCRStatusResponse)
def get_ocr_status() -> OCRStatusResponse:
    active, detail = get_ocr_runtime_status()
    return OCRStatusResponse(active=active, detail=detail)


@router.get("/llm/profiles")
def get_llm_profiles():
    return {"profiles": runtime_settings.get_profiles()}


@router.put("/llm/profiles/{role}")
def update_llm_profile(role: str, payload: ModelProfileRequest):
    try:
        profile = runtime_settings.update_profile(role, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"role": role, "profile": profile}
