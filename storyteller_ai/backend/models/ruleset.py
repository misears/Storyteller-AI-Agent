from typing import Any, Literal

from pydantic import BaseModel, Field

from .state import Tracker


class DiceMechanic(BaseModel):
    kind: Literal["sum_vs_target", "pool_successes", "bands", "roll_under", "custom"]
    default_expression: str
    params: dict[str, Any] = Field(default_factory=dict)
    bands: list[dict[str, Any]] = Field(default_factory=list)
    hook: str | None = None


class StatDef(BaseModel):
    id: str
    label: str
    group: str | None = None
    min: int | None = None
    max: int | None = None
    default: int | None = None


class CheckDef(BaseModel):
    id: str
    label: str
    expression: str
    target_from: str | None = None
    opposed: bool = False


class TurnRules(BaseModel):
    combat_turn_mode: Literal["initiative", "round_robin", "freeform"]
    initiative_check: str | None = None
    actions_per_turn: dict[str, int] = Field(default_factory=dict)


class ChargenStep(BaseModel):
    id: str
    prompt: str
    fills: list[str]
    constraints: dict[str, Any] = Field(default_factory=dict)


class NpcTier(BaseModel):
    id: str
    sheet_profile: Literal["stat_block", "full"]
    required_paths: list[str]


class SourceRef(BaseModel):
    document_id: str
    sha256: str
    role: Literal["core_rules", "supplement_rules", "setting", "reference"]


class Ruleset(BaseModel):
    id: str
    version: str
    name: str
    license: str
    attribution: str | None = None
    dice: DiceMechanic
    attributes: list[StatDef]
    skills: list[StatDef] = Field(default_factory=list)
    resources: list[StatDef] = Field(default_factory=list)
    derived: dict[str, str] = Field(default_factory=dict)
    checks: list[CheckDef]
    turn_rules: TurnRules
    chargen: list[ChargenStep]
    npc_tiers: list[NpcTier]
    sheet_schema: dict[str, Any]
    prompt_digest: str
    family: str | None = None
    outcome_ladder: dict[str, str] = Field(default_factory=dict)
    origin: Literal["bundled", "pdf_import", "manual"] = "bundled"
    source_documents: list[SourceRef] = Field(default_factory=list)
    field_citations: dict[str, str] = Field(default_factory=dict)


class SettingPack(BaseModel):
    id: str
    version: str
    name: str
    compatible_rulesets: list[str]
    genre: list[str]
    tone: list[str]
    default_lines: list[str] = Field(default_factory=list)
    default_veils: list[str] = Field(default_factory=list)
    trackers: list[Tracker] = Field(default_factory=list)
    factions: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    npc_archetypes: list[dict[str, Any]] = Field(default_factory=list)
    name_tables: dict[str, list[str]] = Field(default_factory=dict)
    hook_tables: dict[str, list[str]] = Field(default_factory=dict)
    glossary: dict[str, str] = Field(default_factory=dict)
    lore_document_ids: list[str] = Field(default_factory=list)
    prompt_digest: str