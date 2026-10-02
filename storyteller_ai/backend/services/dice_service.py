from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from ..models.campaign import Actor, Campaign
from ..models.chat import Visibility
from ..models.dice import DiceRoll, DieResult, RngProof
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..persistence.tables import dice_rolls
from ..rules.dice.engine import evaluate
from ..rules.dice.rng import verify_draws


class DiceService:
    def roll(
        self, campaign: Campaign, expression: str, reason: str,
        roller: Actor | None = None, character_id: str | None = None,
        target: int | None = None, mechanic: str = "sum_vs_target",
        params: dict | None = None, visibility: Visibility | None = None,
        session_id: str | None = None, scene_id: str | None = None,
        turn_id: str | None = None, references: dict[str, int] | None = None,
    ) -> DiceRoll:
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                result = evaluate(
                    expression, campaign.rng_seed_ref, campaign.active_branch_id,
                    0, references, mechanic, target, params,
                )
                roll_id = str(uuid4())
                message_id = str(uuid4())
                roll = DiceRoll(
                    id=roll_id, campaign_id=campaign.id, branch_id=campaign.active_branch_id,
                    session_id=session_id, scene_id=scene_id, turn_id=turn_id,
                    seq=writer.seq + 1, chat_message_id=message_id,
                    roller=roller or Actor(kind="system"), character_id=character_id,
                    ruleset_id=campaign.ruleset_id, expression=expression,
                    dice=[DieResult.model_validate(item) for item in result.dice],
                    total=result.total, successes=result.successes, target=target,
                    outcome=result.outcome, interpretation=result.interpretation,
                    reason=reason, visibility=visibility or Visibility(),
                    rng=RngProof(seed_ref=campaign.rng_seed_ref,
                                 counter_start=result.counter_start,
                                 counter_end=result.counter_end),
                    created_at=datetime.now(timezone.utc),
                )
                writer.append(
                    "dice.rolled", {"roll": roll.model_dump(mode="json")},
                    Actor(kind="system"), turn_id,
                )
                writer.append("message.posted", {
                    "id": message_id, "speaker_kind": "system", "player_id": None,
                    "character_id": character_id,
                    "content": f"Rolled {expression}: {result.interpretation}",
                    "client_msg_id": None, "session_id": session_id, "scene_id": scene_id,
                    "visibility": roll.visibility.model_dump(), "dice_roll_ids": [roll_id],
                }, Actor(kind="system"), turn_id)
                return roll
        finally:
            engine.dispose()

    def list(
        self, campaign: Campaign, after_seq: int = 0, limit: int = 50,
        character_id: str | None = None,
    ) -> tuple[list[DiceRoll], int | None]:
        engine = create_campaign_engine()
        try:
            query = select(dice_rolls.c.data).where(
                dice_rolls.c.campaign_id == campaign.id,
                dice_rolls.c.branch_id == campaign.active_branch_id,
                dice_rolls.c.seq > after_seq,
            )
            if character_id is not None:
                query = query.where(dice_rolls.c.character_id == character_id)
            with engine.connect() as connection:
                data = connection.scalars(
                    query.order_by(dice_rolls.c.seq).limit(limit + 1)
                ).all()
            rolls = [DiceRoll.model_validate(item) for item in data[:limit]]
            return rolls, (rolls[-1].seq if len(data) > limit else None)
        finally:
            engine.dispose()

    def verify(self, campaign: Campaign, roll_id: str) -> dict:
        engine = create_campaign_engine()
        try:
            with engine.connect() as connection:
                data = connection.scalar(select(dice_rolls.c.data).where(
                    dice_rolls.c.campaign_id == campaign.id,
                    dice_rolls.c.branch_id == campaign.active_branch_id,
                    dice_rolls.c.id == roll_id,
                ))
            if data is None:
                raise KeyError(f"Roll {roll_id} not found")
            roll = DiceRoll.model_validate(data)
            values, counter_end = verify_draws(
                campaign.rng_seed_ref, campaign.active_branch_id,
                roll.rng.counter_start, [die.sides for die in roll.dice],
            )
            recorded = [die.value for die in roll.dice]
            return {
                "roll_id": roll_id, "valid": values == recorded and counter_end == roll.rng.counter_end,
                "recorded": recorded, "derived": values,
                "counter_start": roll.rng.counter_start, "counter_end": counter_end,
            }
        finally:
            engine.dispose()


dice_service = DiceService()
