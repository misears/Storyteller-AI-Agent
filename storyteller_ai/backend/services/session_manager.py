from typing import Dict, List, Optional

from ..engines.gm_loop import GMLoop
from ..models.campaign import Actor
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from .campaign_service import campaign_service


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(
        self,
        mode: str = "group",
        title: Optional[str] = "",
        setting: Optional[str] = "",
        document_ids: Optional[List[str]] = None,
        campaign_genres: Optional[List[str]] = None,
    ) -> str:
        campaign = campaign_service.create(
            title=title or "", mode=mode, setting=setting or "",
            document_ids=document_ids, campaign_genres=campaign_genres,
        )
        session_id = campaign.id
        if document_ids is None:
            document_ids = []
        if campaign_genres is None:
            campaign_genres = []

        loop = GMLoop(mode)
        loop.orchestrator.state["campaign"] = {
            "title": title or "",
            "setting": setting or "",
            "document_ids": document_ids,
            "campaign_genres": campaign_genres,
        }

        self.sessions[session_id] = {
            "mode": mode,
            "title": title or "",
            "setting": setting or "",
            "document_ids": document_ids,
            "campaign_genres": campaign_genres,
            "characters": [],
            "gm_loop": loop,
        }
        return session_id

    def get_loop(self, session_id: str) -> GMLoop:
        return self.get_session(session_id)["gm_loop"]

    def get_session(self, session_id: str) -> dict:
        if session_id not in self.sessions:
            campaign = campaign_service.get(session_id)
            if campaign is None:
                raise KeyError(f"Session {session_id} not found")
            loop = GMLoop(campaign.mode.value)
            loop.orchestrator.state["campaign"] = {
                "title": campaign.title, "setting": campaign.setting_pack_id,
                "document_ids": campaign.source_document_ids,
                "campaign_genres": (campaign.bible or {}).get("legacy_campaign_genres", []),
            }
            engine = create_campaign_engine()
            try:
                characters = [event.payload["character"] for event in EventStore(engine).read(session_id)
                              if event.type == "character.created"]
            finally:
                engine.dispose()
            loop.orchestrator.state["characters"] = characters
            self.sessions[session_id] = {
                "mode": campaign.mode.value, "title": campaign.title,
                "setting": campaign.setting_pack_id,
                "document_ids": campaign.source_document_ids,
                "campaign_genres": (campaign.bible or {}).get("legacy_campaign_genres", []),
                "characters": characters, "gm_loop": loop,
            }
        return self.sessions[session_id]

    def add_character(self, session_id: str, character: dict) -> list[dict]:
        session = self.get_session(session_id)
        campaign = campaign_service.get(session_id)
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(session_id, campaign.active_branch_id) as writer:
                writer.append("character.created", {"character": character}, Actor(kind="system"))
        finally:
            engine.dispose()
        session.setdefault("characters", []).append(character)
        session["gm_loop"].orchestrator.state.setdefault("characters", []).append(character)
        return session["characters"]

    def list_sessions(self) -> Dict[str, dict]:
        for campaign in campaign_service.list():
            self.get_session(campaign.id)
        return self.sessions


session_manager = SessionManager()
