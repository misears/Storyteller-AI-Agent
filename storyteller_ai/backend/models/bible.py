from pydantic import BaseModel, Field


class Act(BaseModel):
    title: str
    goal: str
    key_beats: list[str] = Field(default_factory=list)
    climax: str = ""


class FactionEntry(BaseModel):
    name: str
    goal: str
    pressure: int = 1


class NpcSeed(BaseModel):
    name: str
    tier: str = "notable"
    role: str
    want: str
    secret: str = ""
    faction_id: str | None = None


class LocationSeed(BaseModel):
    name: str
    purpose: str
    atmosphere: str = ""


class Hook(BaseModel):
    id: str
    text: str
    tied_to: str
    for_character_id: str | None = None


class CampaignBible(BaseModel):
    premise: str
    pitch_for_players: str
    themes: list[str] = Field(min_length=1)
    acts: list[Act] = Field(min_length=1)
    factions: list[FactionEntry] = Field(default_factory=list)
    key_npcs: list[NpcSeed] = Field(default_factory=list)
    locations: list[LocationSeed] = Field(default_factory=list)
    hooks: list[Hook] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    opening_situation: str