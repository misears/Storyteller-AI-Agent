import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .app_paths import get_data_dir

STORE_PATH = get_data_dir() / "character_sheets.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CharacterSheetStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self._lock = Lock()
        self._payload = self._load_payload()

    @staticmethod
    def default_templates() -> List[Dict[str, Any]]:
        return [
            {
                "key": "fantasy-hero-player",
                "name": "Fantasy Hero (Player)",
                "genre": "fantasy",
                "audience": "player",
                "description": "For high fantasy player characters.",
                "field_schema": [
                    {"name": "archetype", "label": "Archetype", "type": "text"},
                    {"name": "ancestry", "label": "Ancestry", "type": "text"},
                    {"name": "background", "label": "Background", "type": "textarea"},
                    {"name": "bonds", "label": "Bonds", "type": "textarea"},
                    {"name": "gear", "label": "Key Gear", "type": "textarea"},
                    {"name": "vitality", "label": "Vitality", "type": "number"},
                    {"name": "mana", "label": "Mana", "type": "number"},
                ],
                "defaults": {
                    "archetype": "",
                    "ancestry": "",
                    "background": "",
                    "bonds": "",
                    "gear": "",
                    "vitality": 10,
                    "mana": 5,
                },
            },
            {
                "key": "fantasy-storyteller-npc",
                "name": "Fantasy NPC Board (Storyteller)",
                "genre": "fantasy",
                "audience": "storyteller",
                "description": "For tracking key NPCs and faction pressure.",
                "field_schema": [
                    {"name": "role", "label": "Narrative Role", "type": "text"},
                    {"name": "faction", "label": "Faction", "type": "text"},
                    {"name": "secrets", "label": "Secrets", "type": "textarea"},
                    {"name": "goals", "label": "Current Goals", "type": "textarea"},
                    {"name": "threat", "label": "Threat Rating", "type": "number"},
                    {"name": "status", "label": "Status", "type": "text"},
                ],
                "defaults": {
                    "role": "",
                    "faction": "",
                    "secrets": "",
                    "goals": "",
                    "threat": 1,
                    "status": "active",
                },
            },
            {
                "key": "sci-fi-operative-player",
                "name": "Sci-Fi Operative (Player)",
                "genre": "sci-fi",
                "audience": "player",
                "description": "For crews, pilots, and agents in futuristic campaigns.",
                "field_schema": [
                    {"name": "origin_world", "label": "Origin World", "type": "text"},
                    {"name": "specialty", "label": "Specialty", "type": "text"},
                    {"name": "cybernetics", "label": "Cybernetics", "type": "textarea"},
                    {"name": "crew_role", "label": "Crew Role", "type": "text"},
                    {"name": "stress", "label": "Stress", "type": "number"},
                    {"name": "hull", "label": "Suit/Hull Integrity", "type": "number"},
                ],
                "defaults": {
                    "origin_world": "",
                    "specialty": "",
                    "cybernetics": "",
                    "crew_role": "",
                    "stress": 0,
                    "hull": 10,
                },
            },
            {
                "key": "horror-investigator-player",
                "name": "Horror Investigator (Player)",
                "genre": "horror",
                "audience": "player",
                "description": "For investigation and survival-focused games.",
                "field_schema": [
                    {"name": "occupation", "label": "Occupation", "type": "text"},
                    {"name": "anchor", "label": "Anchor to Reality", "type": "text"},
                    {"name": "trauma", "label": "Trauma Notes", "type": "textarea"},
                    {"name": "clues", "label": "Known Clues", "type": "textarea"},
                    {"name": "health", "label": "Health", "type": "number"},
                    {"name": "sanity", "label": "Sanity", "type": "number"},
                ],
                "defaults": {
                    "occupation": "",
                    "anchor": "",
                    "trauma": "",
                    "clues": "",
                    "health": 8,
                    "sanity": 8,
                },
            },
            {
                "key": "horror-storyteller-threat",
                "name": "Horror Threat Clock (Storyteller)",
                "genre": "horror",
                "audience": "storyteller",
                "description": "For pacing dread, clues, and manifestations.",
                "field_schema": [
                    {"name": "entity", "label": "Entity", "type": "text"},
                    {"name": "omen", "label": "Current Omen", "type": "textarea"},
                    {"name": "weakness", "label": "Known Weakness", "type": "text"},
                    {"name": "clock", "label": "Dread Clock (0-12)", "type": "number"},
                    {"name": "locations", "label": "Hot Locations", "type": "textarea"},
                ],
                "defaults": {
                    "entity": "",
                    "omen": "",
                    "weakness": "",
                    "clock": 0,
                    "locations": "",
                },
            },
            {
                "key": "noir-detective-player",
                "name": "Noir Detective (Player)",
                "genre": "noir",
                "audience": "player",
                "description": "For mystery, intrigue, and hardboiled city stories.",
                "field_schema": [
                    {"name": "vice", "label": "Vice", "type": "text"},
                    {"name": "contact", "label": "Reliable Contact", "type": "text"},
                    {"name": "case_notes", "label": "Case Notes", "type": "textarea"},
                    {"name": "heat", "label": "Heat", "type": "number"},
                    {"name": "grit", "label": "Grit", "type": "number"},
                ],
                "defaults": {
                    "vice": "",
                    "contact": "",
                    "case_notes": "",
                    "heat": 0,
                    "grit": 6,
                },
            },
        ]

    def _load_payload(self) -> Dict[str, Any]:
        if not self.store_path.exists():
            return {"templates": self.default_templates(), "sheets": {}}

        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        raw.setdefault("templates", self.default_templates())
        raw.setdefault("sheets", {})
        return raw

    def _write_payload(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.store_path.with_name(self.store_path.name + "." + str(uuid4()) + ".tmp")
        try:
            temporary.write_text(json.dumps(self._payload, indent=2, ensure_ascii=True), encoding="utf-8")
            temporary.replace(self.store_path)
        finally:
            temporary.unlink(missing_ok=True)

    def list_templates(self, genre: Optional[str] = None, audience: Optional[str] = None) -> List[Dict[str, Any]]:
        templates = self._payload.get("templates", [])
        filtered: List[Dict[str, Any]] = []
        for template in templates:
            if genre and template.get("genre") != genre:
                continue
            if audience and template.get("audience") != audience:
                continue
            filtered.append(template)
        return filtered

    def get_template(self, template_key: str) -> Dict[str, Any]:
        for template in self._payload.get("templates", []):
            if template.get("key") == template_key:
                return template
        raise KeyError(f"Template {template_key} not found")

    def list_sheets(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sheets = list(self._payload.get("sheets", {}).values())
        if session_id is None:
            return sheets
        return [sheet for sheet in sheets if sheet.get("session_id") == session_id]

    def create_sheet(
        self,
        template_key: str,
        name: str,
        session_id: Optional[str],
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        template = self.get_template(template_key)
        merged_fields = dict(template.get("defaults", {}))
        if fields:
            merged_fields.update(fields)

        sheet_id = str(uuid4())
        now = _utc_now_iso()
        sheet = {
            "sheet_id": sheet_id,
            "template_key": template_key,
            "name": name,
            "session_id": session_id,
            "genre": template.get("genre"),
            "audience": template.get("audience"),
            "description": template.get("description", ""),
            "field_schema": template.get("field_schema", []),
            "fields": merged_fields,
            "created_at": now,
            "updated_at": now,
            "version": 1,
            "history": [],
            "campaign_id": None,
            "experience": {"earned": 0, "spent": 0, "available": 0},
            "advancement_requests": [],
            "advancement_ledger": [],
        }
        self._validate_fields(template, merged_fields)

        with self._lock:
            self._payload.setdefault("sheets", {})[sheet_id] = sheet
            self._write_payload()
        return sheet

    def get_sheet(self, sheet_id: str) -> Dict[str, Any]:
        sheets = self._payload.get("sheets", {})
        if sheet_id not in sheets:
            raise KeyError(f"Sheet {sheet_id} not found")
        return sheets[sheet_id]

    def update_sheet(
        self,
        sheet_id: str,
        name: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
        expected_version: Optional[int] = None,
        reason: str = "sheet update",
    ) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            if sheet.get("campaign_id"):
                raise SheetValidationError("Linked sheets require AI review and human Storyteller approval. Submit an advancement request.")
            current_version = sheet.get("version", 1)
            if expected_version is not None and expected_version != current_version:
                raise SheetConflictError(current_version)
            previous = {
                "version": current_version,
                "name": sheet.get("name"),
                "fields": dict(sheet.get("fields", {})),
                "updated_at": sheet.get("updated_at"),
                "reason": reason,
            }
            if name is not None:
                sheet["name"] = name
            if fields is not None:
                current_fields = dict(sheet.get("fields", {}))
                current_fields.update(fields)
                self._validate_fields(self.get_template(sheet["template_key"]), current_fields)
                sheet["fields"] = current_fields
            sheet["version"] = current_version + 1
            sheet.setdefault("history", []).append(previous)
            sheet["updated_at"] = _utc_now_iso()
            self._payload.setdefault("sheets", {})[sheet_id] = sheet
            self._write_payload()
        return sheet

    def list_history(self, sheet_id: str) -> List[Dict[str, Any]]:
        return list(self.get_sheet(sheet_id).get("history", []))

    def link_campaign(self, sheet_id: str, campaign_id: str, expected_version: int) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            if sheet.get("version", 1) != expected_version:
                raise SheetConflictError(sheet.get("version", 1))
            if not campaign_id:
                raise SheetValidationError("A chronicle is required.")
            if sheet.get("campaign_id"):
                if sheet["campaign_id"] != campaign_id:
                    raise SheetValidationError("This sheet is already linked to another chronicle.")
                return sheet
            sheet.setdefault("experience", {"earned": 0, "spent": 0, "available": 0})
            sheet.setdefault("advancement_requests", [])
            sheet.setdefault("advancement_ledger", [])
            sheet["campaign_id"] = campaign_id
            sheet["version"] = expected_version + 1
            sheet["updated_at"] = _utc_now_iso()
            self._write_payload()
            return sheet

    def propose_advancement(
        self, sheet_id: str, kind: str, xp: int, fields: Dict[str, Any],
        reason: str, expected_version: int, name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            if not sheet.get("campaign_id"):
                raise SheetValidationError("Link the sheet to a chronicle first.")
            if sheet.get("version", 1) != expected_version:
                raise SheetConflictError(sheet.get("version", 1))
            if isinstance(xp, bool) or not isinstance(xp, int) or xp < 0:
                raise SheetValidationError("XP must be a non-negative integer.")
            if kind not in {"award", "spend", "change"} or not reason.strip():
                raise SheetValidationError("A valid request type and reason are required.")
            if kind == "award" and (xp == 0 or fields or name is not None):
                raise SheetValidationError("An XP award must be positive and cannot also change the sheet.")
            if kind == "spend" and (xp == 0 or not fields):
                raise SheetValidationError("An advancement needs positive XP cost and field changes.")
            if kind == "change" and (xp != 0 or (not fields and name is None)):
                raise SheetValidationError("A correction needs changes and cannot spend XP.")
            allowed = {definition["name"] for definition in sheet.get("field_schema", [])}
            if set(fields) - allowed:
                raise SheetValidationError("Unknown sheet fields.")
            self._validate_fields(self.get_template(sheet["template_key"]), {**sheet["fields"], **fields})
            request = {
                "id": str(uuid4()), "kind": kind, "xp": xp, "fields": deepcopy(fields),
                "name": name, "reason": reason.strip(), "base_version": expected_version,
                "status": "pending", "ai_review": None, "created_at": _utc_now_iso(),
            }
            sheet.setdefault("advancement_requests", []).append(request)
            self._write_payload()
            return deepcopy(request)

    def get_advancement(self, sheet_id: str, request_id: str) -> Dict[str, Any]:
        request = next((item for item in self.get_sheet(sheet_id).get("advancement_requests", []) if item["id"] == request_id), None)
        if request is None:
            raise KeyError("Advancement request not found")
        return request

    def record_ai_review(self, sheet_id: str, request_id: str, review: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            request = self.get_advancement(sheet_id, request_id)
            if request["status"] in {"approved", "rejected"}:
                raise SheetValidationError("This request has already been decided.")
            if request["base_version"] != sheet.get("version", 1):
                raise SheetConflictError(sheet.get("version", 1))
            if review.get("recommendation") not in {"approve", "reject", "needs_information"} or not review.get("reason"):
                raise SheetValidationError("The AI review is incomplete.")
            request.update({"ai_review": deepcopy(review), "status": "reviewed", "reviewed_at": _utc_now_iso()})
            self._write_payload()
            return deepcopy(request)

    def decide_advancement(
        self, sheet_id: str, request_id: str, approve: bool, reviewer: str, reason: str,
    ) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            request = self.get_advancement(sheet_id, request_id)
            if request["status"] in {"approved", "rejected"}:
                raise SheetValidationError("This request has already been decided.")
            if not reviewer.strip() or not reason.strip():
                raise SheetValidationError("Human Storyteller name and decision reason are required.")
            if approve:
                if request["base_version"] != sheet.get("version", 1):
                    raise SheetConflictError(sheet.get("version", 1))
                if not request.get("ai_review") or request["ai_review"]["recommendation"] != "approve":
                    raise SheetValidationError("A positive AI review is required before human approval.")
                if request["kind"] == "spend" and request["xp"] > sheet["experience"]["available"]:
                    raise SheetValidationError("Not enough available experience points.")
                fields = {**sheet["fields"], **request["fields"]}
                self._validate_fields(self.get_template(sheet["template_key"]), fields)
                sheet.setdefault("history", []).append({
                    "version": sheet["version"], "name": sheet["name"], "fields": deepcopy(sheet["fields"]),
                    "experience": deepcopy(sheet["experience"]), "updated_at": sheet["updated_at"], "reason": reason.strip(),
                })
                sheet["fields"] = fields
                if request.get("name") is not None:
                    sheet["name"] = request["name"]
                if request["kind"] == "award":
                    sheet["experience"]["earned"] += request["xp"]
                elif request["kind"] == "spend":
                    sheet["experience"]["spent"] += request["xp"]
                sheet["experience"]["available"] = sheet["experience"]["earned"] - sheet["experience"]["spent"]
                sheet["version"] += 1
                sheet["updated_at"] = _utc_now_iso()
            request.update({"status": "approved" if approve else "rejected", "decided_by": reviewer.strip(), "decision_reason": reason.strip(), "decided_at": _utc_now_iso()})
            sheet.setdefault("advancement_ledger", []).append(deepcopy(request))
            self._write_payload()
            return sheet

    def revert_sheet(self, sheet_id: str, version: int, expected_version: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            if sheet.get("campaign_id"):
                raise SheetValidationError("Linked sheets cannot bypass advancement approval by reverting history.")
            current_version = sheet.get("version", 1)
            if expected_version is not None and expected_version != current_version:
                raise SheetConflictError(current_version)
            snapshot = next((item for item in sheet.get("history", []) if item["version"] == version), None)
            if snapshot is None:
                raise KeyError(f"Sheet version {version} not found")
            self._validate_fields(self.get_template(sheet["template_key"]), snapshot["fields"])
            sheet["history"].append({
                "version": current_version, "name": sheet.get("name"),
                "fields": dict(sheet.get("fields", {})), "updated_at": sheet.get("updated_at"),
                "reason": f"revert to version {version}",
            })
            sheet["name"] = snapshot["name"]
            sheet["fields"] = dict(snapshot["fields"])
            sheet["version"] = current_version + 1
            sheet["updated_at"] = _utc_now_iso()
            self._write_payload()
            return sheet

    @staticmethod
    def _validate_fields(template: Dict[str, Any], fields: Dict[str, Any]) -> None:
        for definition in template.get("field_schema", []):
            name = definition.get("name")
            value = fields.get(name)
            if definition.get("type") == "number" and value is not None and not isinstance(value, (int, float)):
                raise SheetValidationError(f"field '{name}' must be numeric")


class SheetConflictError(ValueError):
    def __init__(self, current_version: int):
        super().__init__(f"sheet version conflict; current version is {current_version}")
        self.current_version = current_version


class SheetValidationError(ValueError):
    pass


character_sheet_store = CharacterSheetStore(STORE_PATH)
