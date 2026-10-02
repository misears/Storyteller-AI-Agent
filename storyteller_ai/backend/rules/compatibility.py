"""Compatibility rules for campaigns with multiple ruleset families."""

from .registry import PackRegistry
from ..models.ruleset import Ruleset


def validate_ruleset_mix(registry: PackRegistry[Ruleset], ruleset_ids: list[str]) -> dict:
    if not ruleset_ids:
        raise ValueError("a campaign needs at least one ruleset")
    packs = [registry.get(ruleset_id) for ruleset_id in ruleset_ids]
    missing = [ruleset_id for ruleset_id, pack in zip(ruleset_ids, packs) if pack is None]
    if missing:
        raise ValueError(f"unknown rulesets: {', '.join(missing)}")
    families = {pack.family or pack.id for pack in packs}
    return {
        "ruleset_ids": ruleset_ids,
        "families": sorted(families),
        "comparison": "direct" if len(families) == 1 else "outcome_ladder",
    }