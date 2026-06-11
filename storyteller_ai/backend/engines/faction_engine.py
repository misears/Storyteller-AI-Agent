"""
Faction engine: simple clocks and influence.
"""

from typing import Dict, Any, List


def ensure_faction(campaign: Dict[str, Any], name: str) -> Dict[str, Any]:
    factions: List[Dict[str, Any]] = campaign.setdefault("factions", [])
    for f in factions:
        if f.get("name") == name:
            return f
    faction = {"name": name, "clock": 0, "influence": 1}
    factions.append(faction)
    return faction


def tick_faction_clock(campaign: Dict[str, Any], name: str, amount: int = 1) -> Dict[str, Any]:
    faction = ensure_faction(campaign, name)
    faction["clock"] = max(0, faction.get("clock", 0) + amount)
    return faction


def adjust_influence(campaign: Dict[str, Any], name: str, delta: int) -> Dict[str, Any]:
    faction = ensure_faction(campaign, name)
    faction["influence"] = max(0, faction.get("influence", 1) + delta)
    return faction
