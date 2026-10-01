from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = 1
Id = str


class GMMode(StrEnum):
    SOLO = "solo"
    GROUP = "group"
    ASSISTANT = "assistant"


class PackRef(BaseModel):
    id: str
    version: str


class TurnPolicy(BaseModel):
    mode: Literal["freeform", "round_robin", "initiative"] = "freeform"
    declare_window_seconds: int = 0
    resolve_when_all_declared: bool = True


class TableConfig(BaseModel):
    max_players: int = Field(default=10, ge=1)
    tone: list[str] = Field(default_factory=list)
    lines: list[str] = Field(default_factory=list)
    veils: list[str] = Field(default_factory=list)
    content_rating: Literal["G", "PG", "PG-13", "R"] = "PG-13"
    turn_policy: TurnPolicy = Field(default_factory=TurnPolicy)
    dice_visibility: Literal["all_public", "gm_secret_allowed"] = "gm_secret_allowed"
    absent_pc_policy: Literal["background", "npc_controlled", "ask_table"] = "background"


class Actor(BaseModel):
    kind: Literal["player", "ai_gm", "human_gm", "system"]
    id: Id | None = None


class Campaign(BaseModel):
    id: Id
    schema_version: int = SCHEMA_VERSION
    title: str
    status: Literal["session_zero", "active", "paused", "completed", "archived"] = "session_zero"
    mode: GMMode = GMMode.GROUP
    ruleset_id: str
    ruleset_version: str
    extra_rulesets: list[PackRef] = Field(default_factory=list)
    setting_pack_id: str
    setting_pack_version: str
    extra_setting_packs: list[PackRef] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    table_config: TableConfig = Field(default_factory=TableConfig)
    bible: dict[str, Any] | None = None
    llm_profile: str = "default"
    rng_seed_ref: str
    active_branch_id: Id
    created_at: datetime
    updated_at: datetime


class Account(BaseModel):
    id: Id
    username: str
    email: str | None = None
    is_admin: bool = False
    discord_user_id: str | None = None
    created_at: datetime


class Player(BaseModel):
    id: Id
    account_id: Id | None = None
    display_name: str
    created_at: datetime


class Membership(BaseModel):
    campaign_id: Id
    player_id: Id
    role: Literal["player", "human_gm", "observer"] = "player"
    status: Literal["invited", "active", "away", "left"] = "active"
    joined_at: datetime
    left_at: datetime | None = None
    character_ids: list[Id] = Field(default_factory=list)
    active_character_id: Id | None = None


class PlaySession(BaseModel):
    id: Id
    campaign_id: Id
    number: int
    started_at: datetime
    ended_at: datetime | None = None
    attendee_player_ids: list[Id] = Field(default_factory=list)
    recap: str | None = None