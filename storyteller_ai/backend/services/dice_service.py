from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, exists, func, or_, select

from ..models.campaign import Actor, Campaign
from ..models.chat import Visibility
from ..models.dice import DiceRoll, DieResult, RngProof
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore, branch_lineage_filter
from ..persistence.tables import dice_rolls
from ..rules.dice.engine import evaluate
from ..rules.dice.rng import verify_draws


class DiceService:
    @staticmethod
    def current_counter(campaign: Campaign) -> int:
        engine = create_campaign_engine()
        try:
            with engine.connect() as connection:
                data = connection.scalar(
                    select(dice_rolls.c.data)
                    .where(
                        dice_rolls.c.campaign_id == campaign.id,
                        dice_rolls.c.branch_id == campaign.active_branch_id,
                    )
                    .order_by(dice_rolls.c.seq.desc())
                    .limit(1)
                )
            return int((data or {}).get("rng", {}).get("counter_end", 0))
        finally:
            engine.dispose()

    def prepare_roll(
        self, campaign: Campaign, expression: str, reason: str,
        roller: Actor | None = None, character_id: str | None = None,
        target: int | None = None, mechanic: str = "sum_vs_target",
        params: dict | None = None, visibility: Visibility | None = None,
        session_id: str | None = None, scene_id: str | None = None,
        turn_id: str | None = None, references: dict[str, int] | None = None,
        counter_start: int = 0,
    ) -> DiceRoll:
        result = evaluate(
            expression, campaign.rng_seed_ref, campaign.active_branch_id,
            counter_start, references, mechanic, target, params,
        )
        roll_id = str(uuid4())
        return DiceRoll(
            id=roll_id, campaign_id=campaign.id, branch_id=campaign.active_branch_id,
            session_id=session_id, scene_id=scene_id, turn_id=turn_id,
            seq=0, chat_message_id=str(uuid4()),
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
                latest_roll = writer.connection.scalar(
                    select(dice_rolls.c.data)
                    .where(
                        dice_rolls.c.campaign_id == campaign.id,
                        dice_rolls.c.branch_id == campaign.active_branch_id,
                    )
                    .order_by(dice_rolls.c.seq.desc())
                    .limit(1)
                )
                counter_start = int((latest_roll or {}).get("rng", {}).get("counter_end", 0))
                roll = self.prepare_roll(
                    campaign, expression, reason, roller, character_id, target,
                    mechanic, params, visibility, session_id, scene_id, turn_id,
                    references, counter_start,
                ).model_copy(update={"seq": writer.seq + 1})
                writer.append(
                    "dice.rolled", {"roll": roll.model_dump(mode="json")},
                    Actor(kind="system"), turn_id,
                )
                writer.append("message.posted", {
                    "id": roll.chat_message_id, "speaker_kind": "system", "player_id": None,
                    "character_id": character_id,
                    "content": f"Rolled {expression}: {roll.interpretation}",
                    "client_msg_id": None, "session_id": session_id, "scene_id": scene_id,
                    "visibility": roll.visibility.model_dump(), "dice_roll_ids": [roll.id],
                }, Actor(kind="system"), turn_id)
                return roll
        finally:
            engine.dispose()

    def list(
        self, campaign: Campaign, after_seq: int = 0, limit: int = 50,
        character_id: str | None = None, viewer: str = "player",
        player_id: str | None = None,
    ) -> tuple[list[DiceRoll], int | None]:
        engine = create_campaign_engine()
        try:
            with engine.connect() as connection:
                query = select(dice_rolls.c.data).where(
                    dice_rolls.c.campaign_id == campaign.id,
                    branch_lineage_filter(connection, campaign.id, campaign.active_branch_id, dice_rolls),
                    dice_rolls.c.seq > after_seq,
                )
                if character_id is not None:
                    query = query.where(dice_rolls.c.character_id == character_id)
                if viewer != "gm":
                    scope = dice_rolls.c.data["visibility"]["scope"].as_string()
                    visible_scopes = [scope == "public"]
                    if player_id:
                        recipients = func.json_each(
                            dice_rolls.c.data, "$.visibility.player_ids",
                        ).table_valued("key", "value").alias("dice_recipients")
                        visible_scopes.append(and_(
                            scope == "players",
                            exists(select(1).select_from(recipients).where(
                                recipients.c.value == player_id,
                            )),
                        ))
                    query = query.where(or_(*visible_scopes))
                data = connection.scalars(
                    query.order_by(dice_rolls.c.seq).limit(limit + 1)
                ).all()
            rolls = [DiceRoll.model_validate(item) for item in data[:limit]]
            return rolls, (rolls[-1].seq if len(data) > limit else None)
        finally:
            engine.dispose()

    def verify(
        self, campaign: Campaign, roll_id: str, viewer: str = "player",
        player_id: str | None = None,
    ) -> dict:
        engine = create_campaign_engine()
        try:
            with engine.connect() as connection:
                data = connection.scalar(select(dice_rolls.c.data).where(
                    dice_rolls.c.campaign_id == campaign.id,
                    dice_rolls.c.id == roll_id,
                ))
            if data is None:
                raise KeyError(f"Roll {roll_id} not found")
            roll = DiceRoll.model_validate(data)
            if viewer != "gm" and (
                roll.visibility.scope == "gm_only"
                or (roll.visibility.scope == "players" and player_id not in roll.visibility.player_ids)
            ):
                raise KeyError(f"Roll {roll_id} not found")
            values, counter_end = verify_draws(
                campaign.rng_seed_ref, roll.branch_id,
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
