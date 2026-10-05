import asyncio
from collections.abc import Callable, Iterable
from uuid import uuid4

from starlette.concurrency import run_in_threadpool
from sqlalchemy import select

from ..models.campaign import Actor
from ..persistence.event_store import EventStore, EventWriter
from ..persistence.tables import turns


class TurnService:
    def __init__(self, store: EventStore):
        self.store = store
        self.locks: dict[str, asyncio.Lock] = {}

    async def run(
        self, campaign_id: str, branch_id: str, actor: Actor, content: str,
        dice_rolls: Iterable[dict], resolve: Callable[[EventWriter, str], None],
        client_msg_id: str | None = None,
        turn_id: str | None = None,
    ) -> str:
        lock = self.locks.setdefault(campaign_id, asyncio.Lock())
        async with lock:
            return await run_in_threadpool(
                self._run, campaign_id, branch_id, actor, content, dice_rolls, resolve,
                client_msg_id, turn_id,
            )

    def _run(
        self, campaign_id: str, branch_id: str, actor: Actor, content: str,
        dice_rolls: Iterable[dict], resolve: Callable[[EventWriter, str], None],
        client_msg_id: str | None = None,
        turn_id: str | None = None,
    ) -> str:
        turn_id = turn_id or str(uuid4())
        with self.store.transaction(campaign_id, branch_id) as writer:
            writer.append("message.posted", {
                "id": str(uuid4()), "speaker_kind": "player", "player_id": actor.id,
                "content": content, "client_msg_id": client_msg_id,
            }, actor, turn_id)
            writer.append("turn.started", {"id": turn_id}, actor, turn_id)
            for roll in dice_rolls:
                roll_payload = {**roll, "seq": writer.seq + 1, "turn_id": turn_id}
                writer.append("dice.rolled", {"roll": roll_payload}, Actor(kind="system"), turn_id)
                writer.append("message.posted", {
                    "id": roll_payload["chat_message_id"],
                    "speaker_kind": "system",
                    "player_id": None,
                    "character_id": roll_payload.get("character_id"),
                    "content": f"Rolled {roll_payload['expression']}: {roll_payload['interpretation']}",
                    "client_msg_id": None,
                    "session_id": roll_payload.get("session_id"),
                    "scene_id": roll_payload.get("scene_id"),
                    "visibility": roll_payload.get("visibility", {"scope": "public", "player_ids": []}),
                    "dice_roll_ids": [roll_payload["id"]],
                }, Actor(kind="system"), turn_id)
            resolve(writer, turn_id)
            writer.append("turn.completed", {"id": turn_id}, Actor(kind="system"), turn_id)
        return turn_id

    def recover_incomplete(self, campaign_id: str, branch_id: str) -> list[str]:
        with self.store.engine.connect() as connection:
            ids = connection.scalars(select(turns.c.id).where(
                turns.c.campaign_id == campaign_id,
                turns.c.branch_id == branch_id,
                turns.c.status == "in_progress",
            )).all()
        for turn_id in ids:
            with self.store.transaction(campaign_id, branch_id) as writer:
                writer.append("turn.interrupted", {"id": turn_id}, Actor(kind="system"), turn_id)
        return ids