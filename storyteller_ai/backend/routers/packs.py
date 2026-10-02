from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..rules.registry import pack_registry
from ..services.pack_importer import pack_importer

router = APIRouter(tags=["packs"])


class PackSummary(BaseModel):
    id: str
    version: str
    name: str
    source: str
    mechanic: str | None = None
    validation_error: str | None = None


def _ruleset_summary(entry) -> PackSummary:
    return PackSummary(
        id=entry.value.id if entry.value else entry.path.name,
        version=entry.value.version if entry.value else "",
        name=entry.value.name if entry.value else entry.path.name,
        source=entry.source,
        mechanic=entry.value.dice.kind if entry.value else None,
        validation_error=entry.error,
    )


@router.get("/rulesets", response_model=list[PackSummary])
def list_rulesets(include_invalid: bool = Query(default=False)):
    pack_registry.rulesets.refresh()
    entries = pack_registry.rulesets.list(include_invalid)
    return [_ruleset_summary(entry) for entry in entries]


@router.get("/rulesets/{ruleset_id}")
def get_ruleset(ruleset_id: str, version: str | None = None) -> dict[str, Any]:
    pack_registry.rulesets.refresh()
    ruleset = pack_registry.rulesets.get(ruleset_id, version)
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    return ruleset.model_dump(mode="json", exclude={"sheet_schema"})


@router.get("/rulesets/{ruleset_id}/sheet-schema")
def get_sheet_schema(ruleset_id: str, version: str | None = None):
    pack_registry.rulesets.refresh()
    ruleset = pack_registry.rulesets.get(ruleset_id, version)
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    return ruleset.sheet_schema


@router.get("/themes", response_model=list[dict[str, Any]])
def list_themes(ruleset: str | None = None):
    pack_registry.settings.refresh()
    themes = [entry.value for entry in pack_registry.settings.list()]
    if ruleset is not None:
        themes = [theme for theme in themes if ruleset in theme.compatible_rulesets]
    return [theme.model_dump(mode="json") for theme in themes]


@router.get("/themes/{theme_id}")
def get_theme(theme_id: str, version: str | None = None):
    pack_registry.settings.refresh()
    theme = pack_registry.settings.get(theme_id, version)
    if theme is None:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme.model_dump(mode="json")


class ImportStartRequest(BaseModel):
    document_ids: list[str]
    mode: str = "new"
    target_pack_id: str | None = None


class ImportAnswersRequest(BaseModel):
    fields: dict[str, Any]


@router.post("/rulesets/imports")
def start_pack_import(payload: ImportStartRequest):
    try:
        return pack_importer.start(payload.document_ids, payload.mode, payload.target_pack_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/rulesets/imports/{job_id}")
def get_pack_import(job_id: str):
    try:
        return pack_importer.get(job_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rulesets/imports/{job_id}/answers")
def answer_pack_import(job_id: str, payload: ImportAnswersRequest):
    try:
        return pack_importer.answer(job_id, payload.fields).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rulesets/imports/{job_id}/validate")
def validate_pack_import(job_id: str):
    try:
        return pack_importer.validate(job_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/rulesets/imports/{job_id}/commit")
def commit_pack_import(job_id: str):
    try:
        return pack_importer.commit(job_id).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc