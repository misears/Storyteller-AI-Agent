from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .campaign import Actor, Id, SCHEMA_VERSION, TurnPolicy
from .chat import Visibility


class TurnOrder(BaseModel):
    policy: TurnPolicy = Field(default_factory=TurnPolicy)
    order: list[Id] = Field(default_factory=list)
    index: int = 0
    round: int = 0
    initiative: dict[Id, int] = Field(default_factory=dict)


class PendingAction(BaseModel):
    id: Id
    character_id: Id
    player_id: Id | None = None
    chat_message_id: Id
    status: Literal["declared", "awaiting_roll", "resolved", "cancelled"]


class SpotlightStats(BaseModel):
    turns_featured: int = 0
    words_addressed: int = 0
    rolls: int = 0
    last_featured_turn: int | None = None


class Scene(BaseModel):
    id: Id
    title: str
    location_id: str | None = None
    description: str = ""
    present_character_ids: list[Id] = Field(default_factory=list)
    tension: int = Field(default=2, ge=0, le=5)
    kind: Literal["exploration", "social", "combat", "downtime", "montage"] = "exploration"


class Tracker(BaseModel):
    id: str
    label: str
    kind: Literal["clock", "meter"]
    value: int = 0
    max: int
    visibility: Visibility = Field(default_factory=lambda: Visibility(scope="gm_only"))


class ArcProgress(BaseModel):
    current_act: int = 1
    beats_completed: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    campaign_id: Id
    branch_id: Id
    schema_version: int = SCHEMA_VERSION
    head_seq: int = 0
    session_id: Id | None = None
    scene: Scene | None = None
    turn_number: int = 0
    turn_order: TurnOrder = Field(default_factory=TurnOrder)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    spotlight: dict[Id, SpotlightStats] = Field(default_factory=dict)
    trackers: dict[str, Tracker] = Field(default_factory=dict)
    arc: ArcProgress = Field(default_factory=ArcProgress)
    known_locations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    flags: dict[str, Any] = Field(default_factory=dict)
    rng_counter: int = 0
    summary_refs: list[Id] = Field(default_factory=list)
    storyteller_state: dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    seq: int
    campaign_id: Id
    branch_id: Id
    type: str
    payload: dict[str, Any]
    payload_version: int = 1
    actor: Actor
    turn_id: Id | None = None
    created_at: datetime


class ContextSnapshot(BaseModel):
    campaign_summary_id: Id | None = None
    session_summary_id: Id | None = None
    scene_summary_id: Id | None = None
    verbatim_window_from_seq: int


class SaveSnapshot(BaseModel):
    id: Id
    campaign_id: Id
    branch_id: Id
    name: str
    kind: Literal["auto", "manual", "scene_end", "session_end", "pre_load", "pre_migration"]
    event_seq: int
    state: GameState
    context: ContextSnapshot
    app_version: str
    schema_version: int
    ruleset_version: str
    setting_pack_version: str
    checksum: str
    created_at: datetime