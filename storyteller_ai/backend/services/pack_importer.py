"""Resumable, data-only ruleset pack import workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

from ..models.ruleset import Ruleset
from ..rules.registry import pack_registry
from .app_paths import get_data_dir
from .document_store import document_store


class ImportJob(BaseModel):
    id: str
    document_ids: list[str]
    mode: str = "new"
    target_pack_id: str | None = None
    status: str = "classified"
    classification: dict[str, str] = Field(default_factory=dict)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    draft: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    updated_at: datetime


class PackImporter:
    def __init__(self, documents=None):
        self.job_dir = get_data_dir() / "packs" / "import_jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.documents = documents or document_store

    def start(self, document_ids: list[str], mode: str = "new", target_pack_id: str | None = None) -> ImportJob:
        if not document_ids:
            raise ValueError("at least one source document is required")
        if mode not in {"new", "extend"}:
            raise ValueError("mode must be 'new' or 'extend'")
        available = {item["document_id"] for item in self.documents.list_documents()}
        missing = sorted(set(document_ids) - available)
        if missing:
            raise ValueError(f"unknown source documents: {', '.join(missing)}")
        job_id = str(uuid4())
        classification = {
            document_id: self._classify(document_id) for document_id in document_ids
        }
        draft = self._base_draft(job_id, mode, target_pack_id, document_ids)
        job = ImportJob(
            id=job_id, document_ids=document_ids, mode=mode,
            target_pack_id=target_pack_id, classification=classification,
            questions=[{"id": "confirm_system", "prompt": "Confirm the detected system."}],
            draft=draft, updated_at=datetime.now(timezone.utc),
        )
        self._save(job)
        return job

    def get(self, job_id: str) -> ImportJob:
        path = self.job_dir / f"{job_id}.json"
        if not path.is_file():
            raise KeyError(f"import job {job_id} not found")
        return ImportJob.model_validate_json(path.read_text(encoding="utf-8"))

    def answer(self, job_id: str, fields: dict[str, Any]) -> ImportJob:
        job = self.get(job_id)
        job.draft = _merge(job.draft, fields)
        job.status = "draft"
        job.questions = []
        job.updated_at = datetime.now(timezone.utc)
        self._save(job)
        return job

    def validate(self, job_id: str) -> ImportJob:
        job = self.get(job_id)
        job.errors = []
        try:
            manifest = {**job.draft["manifest"], "sheet_schema": job.draft["sheet_schema"]}
            Ruleset.model_validate(manifest)
            Draft202012Validator.check_schema(job.draft["sheet_schema"])
            job.status = "validated"
        except Exception as exc:
            job.status = "invalid"
            job.errors.append(str(exc))
        job.updated_at = datetime.now(timezone.utc)
        self._save(job)
        return job

    def commit(self, job_id: str) -> ImportJob:
        job = self.get(job_id)
        if job.status != "validated":
            raise ValueError("import job must pass validation before commit")
        manifest = dict(job.draft["manifest"])
        pack_dir = get_data_dir() / "packs" / "rulesets" / manifest["id"]
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "ruleset.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        (pack_dir / "sheet.schema.json").write_text(
            json.dumps(job.draft["sheet_schema"], indent=2), encoding="utf-8"
        )
        job.status = "committed"
        job.updated_at = datetime.now(timezone.utc)
        self._save(job)
        pack_registry.refresh()
        return job

    def _base_draft(self, job_id: str, mode: str, target: str | None, document_ids: list[str]) -> dict[str, Any]:
        pack_id = target or f"imported-{job_id[:8]}"
        version = "1.0.0"
        if mode == "extend" and target:
            existing = pack_registry.rulesets.get(target)
            if existing is not None:
                pack_id = existing.id
                major, minor, patch = (int(value) for value in existing.version.split("."))
                version = f"{major}.{minor}.{patch + 1}"
        return {
            "manifest": {
                "id": pack_id, "version": version, "name": "Imported Ruleset",
                "license": "Local import", "attribution": "Generated from selected local documents",
                "dice": {"kind": "sum_vs_target", "default_expression": "1d20"},
                "attributes": [], "skills": [], "resources": [], "derived": {}, "checks": [],
                "turn_rules": {"combat_turn_mode": "freeform"}, "chargen": [], "npc_tiers": [],
                "prompt_digest": "Use the selected local documents for detailed rules lookup.",
                "family": "imported", "origin": "pdf_import",
                "source_documents": [
                    {"document_id": document_id, "sha256": _document_digest(document_id), "role": "core_rules"}
                    for document_id in document_ids
                ],
            },
            "sheet_schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
        }

    def _classify(self, document_id: str) -> str:
        title = next((item["title"] for item in self.documents.list_documents()
                      if item["document_id"] == document_id), document_id).lower()
        if any(word in title for word in ("setting", "city", "guide")):
            return "setting"
        return "core_rules"

    def _save(self, job: ImportJob) -> None:
        (self.job_dir / f"{job.id}.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")


def _document_digest(document_id: str) -> str:
    return hashlib.sha256(document_id.encode()).hexdigest()


def _merge(original: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = dict(original)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


pack_importer = PackImporter()