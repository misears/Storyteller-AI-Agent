from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .campaign import Actor, Id


class Character(BaseModel):
    id: Id
    campaign_id: Id
    kind: Literal["pc", "npc"]
    name: str
    owner_player_id: Id | None = None
    controller: Literal["player", "ai_gm", "human_gm"] = "player"
    status: Literal["active", "absent", "retired", "dead", "hidden"] = "active"
    npc_tier: str | None = None
    public_description: str = ""
    gm_notes: str = ""
    faction_ids: list[str] = Field(default_factory=list)
    sheet_id: Id
    created_in_turn_id: Id | None = None


class CharacterSheet(BaseModel):
    id: Id
    character_id: Id
    ruleset_id: str
    ruleset_version: str
    version: int
    data: dict[str, Any]
    derived: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
    updated_by: Actor


class SheetVersion(BaseModel):
    sheet_id: Id
    version: int
    data: dict[str, Any]
    patch: list[dict[str, Any]]
    reason: str
    actor: Actor
    turn_id: Id | None
    event_seq: int
    created_at: datetime