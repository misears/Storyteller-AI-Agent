from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.pdf_ingest import get_ocr_runtime_status
from ..services.runtime_settings import runtime_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMSettingsResponse(BaseModel):
    provider: str
    model: str
    ollama_url: str
    ollama_model: str


class LLMSettingsUpdateRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None


class OCRStatusResponse(BaseModel):
    active: bool
    detail: str


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    return runtime_settings.get_llm()


@router.put("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    updates = payload.dict(exclude_none=True)
    if "provider" in updates:
        updates["provider"] = updates["provider"].lower()
    return runtime_settings.update_llm(updates)


@router.get("/ocr", response_model=OCRStatusResponse)
def get_ocr_status() -> OCRStatusResponse:
    active, detail = get_ocr_runtime_status()
    return OCRStatusResponse(active=active, detail=detail)
