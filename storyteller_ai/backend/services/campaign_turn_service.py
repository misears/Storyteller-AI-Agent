from uuid import uuid4

from ..engines.gm_loop import GMLoop
from ..models.campaign import Actor, Campaign
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..services.session_manager import session_manager
from .turn_service import TurnService


class CampaignTurnService:
    async def submit(self, campaign: Campaign, content: str, actor: Actor) -> dict:
        loop: GMLoop = session_manager.get_loop(campaign.id)
        response = await loop.step(content)
        engine = create_campaign_engine()
        try:
            service = TurnService(EventStore(engine))

            def resolve(writer, turn_id: str) -> None:
                writer.append("message.posted", {
                    "id": str(uuid4()), "speaker_kind": "gm", "content": response["text"],
                    "session_id": None, "scene_id": None, "visibility": {"scope": "public"},
                }, Actor(kind="ai_gm"), turn_id)

            turn_id = await service.run(
                campaign.id, campaign.active_branch_id, actor, content, [], resolve,
            )
            return {"turn_id": turn_id, "status": "resolved", "text": response["text"], "mode": loop.mode}
        finally:
            engine.dispose()


campaign_turn_service = CampaignTurnService()