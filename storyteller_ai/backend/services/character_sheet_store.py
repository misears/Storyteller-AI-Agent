import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORE_PATH = DATA_DIR / "character_sheets.json"


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
        self.store_path.write_text(
            json.dumps(self._payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

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
        }

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
    ) -> Dict[str, Any]:
        with self._lock:
            sheet = self.get_sheet(sheet_id)
            if name is not None:
                sheet["name"] = name
            if fields is not None:
                current_fields = dict(sheet.get("fields", {}))
                current_fields.update(fields)
                sheet["fields"] = current_fields
            sheet["updated_at"] = _utc_now_iso()
            self._payload.setdefault("sheets", {})[sheet_id] = sheet
            self._write_payload()
        return sheet


character_sheet_store = CharacterSheetStore(STORE_PATH)
