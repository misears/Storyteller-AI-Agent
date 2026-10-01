from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..models.campaign import Campaign, GMMode
from ..models.chat import ChatMessage, Visibility
from ..models.campaign import Actor
from ..models.dice import DiceRoll
from ..models.state import GameState
from ..services.campaign_service import campaign_service
from ..services.chat_service import chat_service
from ..services.dice_service import dice_service
from ..services.document_store import document_store
from ..services.campaign_turn_service import campaign_turn_service
from ..services.save_service import save_service
from ..services.bible_service import bible_service
from fastapi.responses import Response

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


class DiceRollRequest(BaseModel):
    expression: str
    reason: str
    character_id: str | None = None
    target: int | None = None
    mechanic: str = "sum_vs_target"
    params: dict = Field(default_factory=dict)
    session_id: str | None = None
    scene_id: str | None = None
    turn_id: str | None = None
    visibility: Visibility = Field(default_factory=Visibility)


class DicePage(BaseModel):
    rolls: list[DiceRoll]
    next_after_seq: int | None


class RuleLookupRequest(BaseModel):
    query: str


class RuleLookupResult(BaseModel):
    document_id: str
    title: str
    page: int
    snippet: str


class RuleLookupResponse(BaseModel):
    results: list[RuleLookupResult]


class CampaignTurnRequest(BaseModel):
    content: str
    character_id: str | None = None
    player_id: str | None = None
    client_msg_id: str | None = None
    in_character: bool = True


class SaveRequest(BaseModel):
    name: str


class BibleEditRequest(BaseModel):
    value: object


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


@router.post("/{campaign_id}/dice", response_model=DiceRoll)
def roll_campaign_dice(campaign_id: str, payload: DiceRollRequest):
    campaign = get_campaign(campaign_id)
    try:
        return dice_service.roll(
            campaign, payload.expression, payload.reason, Actor(kind="player"),
            payload.character_id, payload.target, payload.mechanic, payload.params,
            payload.visibility, payload.session_id, payload.scene_id, payload.turn_id,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{campaign_id}/dice", response_model=DicePage)
def get_campaign_dice(
    campaign_id: str, after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100), character_id: str | None = None,
):
    campaign = get_campaign(campaign_id)
    rolls, next_after_seq = dice_service.list(campaign, after_seq, limit, character_id)
    return DicePage(rolls=rolls, next_after_seq=next_after_seq)


@router.get("/{campaign_id}/dice/{roll_id}/verify")
def verify_campaign_dice(campaign_id: str, roll_id: str):
    campaign = get_campaign(campaign_id)
    try:
        return dice_service.verify(campaign, roll_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{campaign_id}/rules/lookup", response_model=RuleLookupResponse)
def lookup_campaign_rules(campaign_id: str, payload: RuleLookupRequest):
    campaign = get_campaign(campaign_id)
    return {"results": document_store.retrieve_scoped(payload.query, campaign.source_document_ids)}


@router.post("/{campaign_id}/turns")
async def submit_campaign_turn(campaign_id: str, payload: CampaignTurnRequest):
    campaign = get_campaign(campaign_id)
    return await campaign_turn_service.submit(
        campaign, payload.content, Actor(kind="player", id=payload.player_id),
    )


@router.post("/{campaign_id}/saves")
def create_campaign_save(campaign_id: str, payload: SaveRequest):
    return save_service.create(get_campaign(campaign_id), payload.name)


@router.get("/{campaign_id}/saves")
def list_campaign_saves(campaign_id: str):
    return {"saves": save_service.list(get_campaign(campaign_id))}


@router.post("/{campaign_id}/saves/{save_id}/load")
def load_campaign_save(campaign_id: str, save_id: str):
    try:
        branch_id = save_service.load(get_campaign(campaign_id), save_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"branch_id": branch_id}


@router.get("/{campaign_id}/export")
def export_campaign(campaign_id: str):
    campaign = get_campaign(campaign_id)
    return Response(save_service.export(campaign), media_type="application/zip")


@router.post("/{campaign_id}/session-zero/bible")
def generate_bible(campaign_id: str, section: str | None = None):
    campaign = get_campaign(campaign_id)
    try:
        bible = bible_service.generate(campaign, section)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"bible": bible.model_dump(mode="json")}


@router.get("/{campaign_id}/session-zero/bible")
def get_bible(campaign_id: str):
    bible = bible_service.get(get_campaign(campaign_id))
    if bible is None:
        raise HTTPException(status_code=404, detail="Campaign bible not found")
    return {"bible": bible.model_dump(mode="json")}


@router.put("/{campaign_id}/session-zero/bible/{section}")
def edit_bible(campaign_id: str, section: str, payload: BibleEditRequest):
    try:
        bible = bible_service.edit(get_campaign(campaign_id), section, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"bible": bible.model_dump(mode="json")}