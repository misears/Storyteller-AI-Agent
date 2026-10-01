from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..models.campaign import Campaign, GMMode
from ..models.chat import ChatMessage, Visibility
from ..models.state import GameState
from ..services.campaign_service import campaign_service
from ..services.chat_service import chat_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    title: str = ""
    mode: GMMode = GMMode.GROUP
    setting: str = ""
    document_ids: list[str] = Field(default_factory=list)
    campaign_genres: list[str] = Field(default_factory=list)


class PostChatRequest(BaseModel):
    content: str
    speaker_kind: Literal["player", "gm", "npc", "system", "tool"] = "player"
    player_id: str | None = None
    client_msg_id: str | None = None
    session_id: str | None = None
    scene_id: str | None = None
    visibility: Visibility = Field(default_factory=Visibility)


class ChatPage(BaseModel):
    messages: list[ChatMessage]
    next_after_seq: int | None


@router.post("/", response_model=Campaign)
def create_campaign(payload: CreateCampaignRequest):
    return campaign_service.create(**payload.model_dump())


@router.get("/", response_model=list[Campaign])
def list_campaigns():
    return campaign_service.list()


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str):
    campaign = campaign_service.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/state", response_model=GameState)
def get_campaign_state(campaign_id: str):
    campaign = get_campaign(campaign_id)
    return campaign_service.state(campaign)


@router.post("/{campaign_id}/chat", response_model=ChatMessage)
def post_chat_message(campaign_id: str, payload: PostChatRequest):
    campaign = get_campaign(campaign_id)
    return chat_service.post(
        campaign_id, campaign.active_branch_id, payload.content,
        payload.speaker_kind, payload.player_id, payload.client_msg_id, payload.visibility,
        payload.session_id, payload.scene_id,
    )


@router.get("/{campaign_id}/chat", response_model=ChatPage)
def get_chat_messages(
    campaign_id: str, after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100), session_id: str | None = None,
    scene_id: str | None = None, speaker_kind: str | None = None,
):
    campaign = get_campaign(campaign_id)
    messages, next_after_seq = chat_service.list(
        campaign_id, campaign.active_branch_id, after_seq, limit,
        session_id, scene_id, speaker_kind,
    )
    return ChatPage(messages=messages, next_after_seq=next_after_seq)