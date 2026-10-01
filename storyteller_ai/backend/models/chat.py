from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .campaign import Id


class Visibility(BaseModel):
    scope: Literal["public", "gm_only", "players"] = "public"
    player_ids: list[Id] = Field(default_factory=list)


class ChatMessage(BaseModel):
    id: Id
    campaign_id: Id
    branch_id: Id
    session_id: Id | None = None
    scene_id: Id | None = None
    turn_id: Id | None = None
    seq: int
    speaker_kind: Literal["player", "gm", "npc", "system", "tool"]
    player_id: Id | None = None
    character_id: Id | None = None
    in_character: bool = True
    content: str
    visibility: Visibility = Field(default_factory=Visibility)
    reply_to_id: Id | None = None
    dice_roll_ids: list[Id] = Field(default_factory=list)
    client_msg_id: str | None = None
    created_at: datetime