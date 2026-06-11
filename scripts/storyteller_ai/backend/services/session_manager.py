from typing import Dict
from uuid import uuid4

from ..engines.gm_loop import GMLoop


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self, mode: str = "group") -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "mode": mode,
            "gm_loop": GMLoop(mode),
        }
        return session_id

    def get_loop(self, session_id: str) -> GMLoop:
        return self.sessions[session_id]["gm_loop"]


session_manager = SessionManager()
