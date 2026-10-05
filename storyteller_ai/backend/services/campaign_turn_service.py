import asyncio
from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select

from ..engines.gm_loop import GMLoop
from ..models.campaign import Actor, Campaign
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..persistence.tables import chat_messages, turns
from ..services.session_manager import session_manager
from .turn_service import TurnService


class TurnConflictError(RuntimeError):
    """Raised when a retry refers to a turn that cannot be safely replayed."""


@dataclass
class ActiveTurn:
    task: asyncio.Task
    phase: str = "generating"
    cancelled: bool = False


class CampaignTurnService:
    def __init__(self):
        self._campaign_locks: dict[str, asyncio.Lock] = {}
        self._active: dict[tuple[str, str], ActiveTurn] = {}

    async def submit(
        self, campaign: Campaign, content: str, actor: Actor,
        client_msg_id: str | None = None,
    ) -> dict:
        loop: GMLoop = session_manager.get_loop(campaign.id)
        lock = self._campaign_locks.setdefault(campaign.id, asyncio.Lock())
        async with lock:
            engine = create_campaign_engine()
            try:
                if client_msg_id:
                    existing = self._existing_result(
                        engine, campaign.id, campaign.active_branch_id, client_msg_id,
                        content, actor,
                    )
                    if existing is not None:
                        return {**existing, "mode": loop.mode}

                state_before = deepcopy(loop.orchestrator.state)
                request_id = client_msg_id or str(uuid4())
                turn_id = str(uuid4())
                active_key = (campaign.id, request_id)
                active_turn = ActiveTurn(task=asyncio.current_task())
                self._active[active_key] = active_turn
                try:
                    response = await loop.step(content, campaign=campaign, turn_id=turn_id)
                    active_turn.phase = "persisting"
                    service = TurnService(EventStore(engine))

                    def resolve(writer, turn_id: str) -> None:
                        for tool_result in response.get("tool_results", []):
                            writer.append("tool.executed", tool_result, Actor(kind="ai_gm"), turn_id)
                        for patch in response.get("state_updates", []):
                            writer.append("game_state.updated", {"patch": patch}, Actor(kind="ai_gm"), turn_id)
                        writer.append("message.posted", {
                            "id": str(uuid4()), "speaker_kind": "gm", "content": response["text"],
                            "session_id": None, "scene_id": None, "visibility": {"scope": "public"},
                        }, Actor(kind="ai_gm"), turn_id)

                    turn_id = await service.run(
                        campaign.id, campaign.active_branch_id, actor, content,
                        response.get("dice_rolls", []), resolve,
                        client_msg_id=client_msg_id,
                        turn_id=turn_id,
                    )
                    for patch in response.get("state_updates", []):
                        loop.orchestrator.apply_state_update(patch)
                    return {"turn_id": turn_id, "status": "resolved", "text": response["text"], "mode": loop.mode}
                except asyncio.CancelledError:
                    loop.orchestrator.state = state_before
                    if active_turn.cancelled:
                        return {"status": "cancelled", "text": "", "mode": loop.mode}
                    raise
                except BaseException:
                    loop.orchestrator.state = state_before
                    raise
                finally:
                    self._active.pop(active_key, None)
            finally:
                engine.dispose()

    def cancel(self, campaign_id: str, client_msg_id: str) -> bool:
        active_turn = self._active.get((campaign_id, client_msg_id))
        if active_turn is None or active_turn.phase != "generating":
            return False
        active_turn.cancelled = True
        active_turn.task.cancel()
        return True

    @staticmethod
    def _existing_result(
        engine, campaign_id: str, branch_id: str, client_msg_id: str,
        content: str, actor: Actor,
    ) -> dict | None:
        with engine.connect() as connection:
            message = connection.execute(select(
                chat_messages.c.turn_id, chat_messages.c.data,
            ).where(
                chat_messages.c.campaign_id == campaign_id,
                chat_messages.c.client_msg_id == client_msg_id,
            )).first()
            if message is None or message.turn_id is None:
                return None
            if message.data["content"] != content or message.data.get("player_id") != actor.id:
                raise TurnConflictError(
                    "This action ID was already used for different content or a different player. "
                    "Submit a new action with a new ID."
                )
            status = connection.scalar(select(turns.c.status).where(
                turns.c.id == message.turn_id,
                turns.c.campaign_id == campaign_id,
            ))
            if status != "completed":
                raise TurnConflictError(
                    f"This action already has a turn with status '{status or 'unknown'}'. "
                    "Refresh the chronicle before submitting another action."
                )
            gm_message = connection.execute(select(chat_messages.c.data).where(
                chat_messages.c.campaign_id == campaign_id,
                chat_messages.c.branch_id == branch_id,
                chat_messages.c.turn_id == message.turn_id,
                chat_messages.c.speaker_kind == "gm",
            )).first()
        if gm_message is None:
            raise TurnConflictError("This turn is already committed. Refresh the chronicle to view its response.")
        return {
            "turn_id": message.turn_id,
            "status": "resolved",
            "text": gm_message.data["content"],
        }


campaign_turn_service = CampaignTurnService()