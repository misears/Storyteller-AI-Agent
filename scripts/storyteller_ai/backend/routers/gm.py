from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.session_manager import session_manager

router = APIRouter(prefix="/gm", tags=["gm"])


class GMStepRequest(BaseModel):
    session_id: str
    message: str


@router.post("/step")
async def gm_step(payload: GMStepRequest):
    try:
        loop = session_manager.get_loop(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await loop.step(payload.message)
    return result
