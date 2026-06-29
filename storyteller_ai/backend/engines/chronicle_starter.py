"""
Chronicle starter: seeds factions, city, and tone.
"""

from typing import Dict, Any
from .faction_engine import ensure_faction
from .city_map import add_district


def seed_chronicle(state: Dict[str, Any]) -> Dict[str, Any]:
    campaign: Dict[str, Any] = state.setdefault("campaign", {})

    # Factions
    for name in ["Camarilla", "Anarchs", "Sabbat (rumors)"]:
        ensure_faction(campaign, name)

    # City districts
    add_district(campaign, "Downtown", ["Elysium", "Corporate", "Police presence"])
    add_district(campaign, "Industrial Zone", ["Rack", "Gangs", "Smuggling"])
    add_district(campaign, "Old Town", ["Haunted", "Ancient Havens"])

    campaign.setdefault("tone", "personal horror in a neon-soaked city")
    return state
