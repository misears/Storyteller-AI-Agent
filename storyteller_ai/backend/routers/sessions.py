from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    mode: str = "group"
    title: Optional[str] = ""
    setting: Optional[str] = ""
    document_ids: List[str] = Field(default_factory=list)
    campaign_genres: List[str] = Field(default_factory=list)


class CharacterCreateRequest(BaseModel):
    name: str
    clan: Optional[str] = None
    notes: Optional[str] = None


class SessionStatusResponse(BaseModel):
    session_id: str
    mode: str
    state: Dict[str, Any]


@router.get("/", response_model=Dict[str, Any])
def list_all_sessions():
    sessions_dict = {}
    for session_id, session in session_manager.list_sessions().items():
        sessions_dict[session_id] = {
            "mode": session.get("mode"),
            "title": session.get("title", ""),
            "setting": session.get("setting", ""),
            "document_ids": session.get("document_ids", []),
            "campaign_genres": session.get("campaign_genres", []),
            "character_count": len(session.get("characters", [])),
        }
    return {"sessions": sessions_dict}


@router.post("/create")
def create_session(payload: CreateSessionRequest):
    session_id = session_manager.create_session(
        payload.mode,
        title=payload.title,
        setting=payload.setting,
        document_ids=payload.document_ids,
        campaign_genres=payload.campaign_genres,
    )
    return {
        "session_id": session_id,
        "mode": payload.mode,
        "title": payload.title,
        "setting": payload.setting,
        "document_ids": payload.document_ids,
        "campaign_genres": payload.campaign_genres,
    }


@router.post("/{session_id}/characters")
def create_character(session_id: str, payload: CharacterCreateRequest):
    try:
        session = session_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    character = payload.dict()
    session.setdefault("characters", []).append(character)
    gm_loop = session["gm_loop"]
    gm_loop.orchestrator.state.setdefault("characters", []).append(character)
    return {"character": character, "characters": session["characters"]}


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
