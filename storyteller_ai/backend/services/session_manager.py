from typing import Dict, List, Optional
from uuid import uuid4

from ..engines.gm_loop import GMLoop


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(
        self,
        mode: str = "group",
        title: Optional[str] = "",
        setting: Optional[str] = "",
        document_ids: Optional[List[str]] = None,
    ) -> str:
        session_id = str(uuid4())
        if document_ids is None:
            document_ids = []

        loop = GMLoop(mode)
        loop.orchestrator.state["campaign"] = {
            "title": title or "",
            "setting": setting or "",
            "document_ids": document_ids,
        }

        self.sessions[session_id] = {
            "mode": mode,
            "title": title or "",
            "setting": setting or "",
            "document_ids": document_ids,
            "characters": [],
            "gm_loop": loop,
        }
        return session_id

    def get_loop(self, session_id: str) -> GMLoop:
        try:
            return self.sessions[session_id]["gm_loop"]
        except KeyError as exc:
            raise KeyError(f"Session {session_id} not found") from exc

    def get_session(self, session_id: str) -> dict:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Session {session_id} not found") from exc

    def list_sessions(self) -> Dict[str, dict]:
        return self.sessions


session_manager = SessionManager()
