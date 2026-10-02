from datetime import datetime, timezone
from uuid import uuid4

from ..models.bible import CampaignBible
from ..models.campaign import Actor, Campaign, PlaySession
from ..models.character import Character
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..rules.registry import pack_registry


class SessionZeroService:
    def complete(self, campaign: Campaign) -> dict:
        bible_data = (campaign.bible or {}).get("campaign_bible")
        if not bible_data:
            raise ValueError("campaign bible must be generated first")
        bible = CampaignBible.model_validate(bible_data)
        ruleset = pack_registry.rulesets.get(campaign.ruleset_id, campaign.ruleset_version)
        if ruleset is None:
            ruleset = pack_registry.rulesets.get(campaign.ruleset_id)
        if ruleset is None:
            raise ValueError("campaign ruleset is not installed")
        engine = create_campaign_engine()
        scene_id = str(uuid4())
        seeded = []
        try:
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                for npc in bible.key_npcs:
                    character_id = str(uuid4())
                    character = Character(
                        id=character_id, campaign_id=campaign.id, kind="npc", name=npc.name,
                        controller="ai_gm", npc_tier=npc.tier, sheet_id=str(uuid4()),
                        public_description=npc.role,
                    )
                    writer.append("character.created", {"character": character.model_dump(mode="json")}, Actor(kind="system"))
                    seeded.append(character)
                writer.append("scene.started", {"scene": {
                    "id": scene_id, "title": "Opening Scene", "description": bible.opening_situation,
                }}, Actor(kind="system"))
            return {"status": "ready", "scene_id": scene_id, "characters": seeded}
        finally:
            engine.dispose()

    def start_session(self, campaign: Campaign, attendees: list[str] | None = None) -> PlaySession:
        engine = create_campaign_engine()
        session = PlaySession(
            id=str(uuid4()), campaign_id=campaign.id, number=1,
            started_at=datetime.now(timezone.utc), attendee_player_ids=attendees or [],
        )
        try:
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                writer.append("session.started", session.model_dump(mode="json"), Actor(kind="system"))
            return session
        finally:
            engine.dispose()

    def end_session(self, campaign: Campaign, session_id: str, recap: str) -> PlaySession:
        session = PlaySession(
            id=session_id, campaign_id=campaign.id, number=1,
            started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc), recap=recap,
        )
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                writer.append("session.ended", session.model_dump(mode="json"), Actor(kind="system"))
            return session
        finally:
            engine.dispose()


session_zero_service = SessionZeroService()