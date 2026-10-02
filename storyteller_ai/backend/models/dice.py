from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .campaign import Actor, Id
from .chat import Visibility


class DieResult(BaseModel):
    sides: int
    value: int
    kept: bool = True
    exploded: bool = False
    rerolled_from: int | None = None


class Modifier(BaseModel):
    source: str
    value: int


class RngProof(BaseModel):
    algorithm: Literal["hmac-sha256-ctr-v1"] = "hmac-sha256-ctr-v1"
    seed_ref: str
    counter_start: int
    counter_end: int


class DiceRoll(BaseModel):
    id: Id
    campaign_id: Id
    branch_id: Id
    session_id: Id | None = None
    scene_id: Id | None = None
    turn_id: Id | None = None
    seq: int
    chat_message_id: Id
    roller: Actor
    character_id: Id | None = None
    ruleset_id: str
    check_id: str | None = None
    expression: str
    dice: list[DieResult]
    modifiers: list[Modifier] = Field(default_factory=list)
    total: int | None = None
    successes: int | None = None
    target: int | None = None
    outcome: Literal["critical_success", "success", "partial", "failure", "critical_failure", "botch"] | None = None
    interpretation: str
    reason: str
    visibility: Visibility = Field(default_factory=Visibility)
    rng: RngProof
    created_at: datetime