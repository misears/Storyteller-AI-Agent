from fastapi import APIRouter
from pydantic import BaseModel
from ..services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    mode: str = "group"


@router.post("/create")
def create_session(payload: CreateSessionRequest):
    session_id = session_manager.create_session(payload.mode)
    return {"session_id": session_id, "mode": payload.mode}
