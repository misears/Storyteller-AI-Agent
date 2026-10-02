from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from ..models.character import Character, CharacterSheet
from ..models.ruleset import Ruleset
from ..rules.formulas import FormulaError, evaluate_formula


def validate_sheet(ruleset: Ruleset, data: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(ruleset.sheet_schema).iter_errors(data), key=lambda error: error.path)
    if errors:
        raise ValueError(errors[0].message)


def derive_sheet_values(ruleset: Ruleset, data: dict[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in data.items() if isinstance(value, (int, float))}
    derived = {}
    for name, formula in ruleset.derived.items():
        try:
            derived[name] = evaluate_formula(formula, values)
        except FormulaError as exc:
            raise ValueError(f"invalid derived formula {name}: {exc}") from exc
    return derived


def build_character_sheet(
    ruleset: Ruleset, character: Character, data: dict[str, Any], actor,
) -> CharacterSheet:
    validate_sheet(ruleset, data)
    return CharacterSheet(
        id=character.sheet_id, character_id=character.id,
        ruleset_id=ruleset.id, ruleset_version=ruleset.version,
        version=1, data=data, derived=derive_sheet_values(ruleset, data),
        updated_at=datetime.now(timezone.utc),
        updated_by=actor,
    )


def build_npc_sheet(ruleset: Ruleset, character: Character, tier: str, data: dict[str, Any], actor) -> CharacterSheet:
    tier_definition = next((item for item in ruleset.npc_tiers if item.id == tier), None)
    if tier_definition is None:
        raise ValueError(f"unknown NPC tier: {tier}")
    missing = [path for path in tier_definition.required_paths if _path_value(data, path) is None]
    if missing:
        raise ValueError(f"NPC tier requires fields: {', '.join(missing)}")
    return build_character_sheet(ruleset, character, data, actor)


def _path_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.strip("/").split("/"):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current