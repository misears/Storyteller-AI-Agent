from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
from ..services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    mode: str = "group"


class SessionStatusResponse(BaseModel):
    session_id: str
    mode: str
    state: Dict[str, Any]


@router.post("/create")
def create_session(payload: CreateSessionRequest):
    session_id = session_manager.create_session(payload.mode)
    return {"session_id": session_id, "mode": payload.mode}


@router.get("/{session_id}", response_model=SessionStatusResponse)
def get_session_status(session_id: str):
    try:
        session = session_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    gm_loop = session["gm_loop"]
    return {
        "session_id": session_id,
        "mode": session["mode"],
        "state": gm_loop.orchestrator.state,
    }
