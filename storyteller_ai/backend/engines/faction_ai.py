"""
Faction AI: suggests next moves based on clocks.
"""

from typing import Dict, Any, List


def suggest_faction_moves(campaign: Dict[str, Any]) -> List[str]:
    factions = campaign.get("factions", [])
    suggestions: List[str] = []

    for f in factions:
        name = f.get("name", "Unknown Faction")
        clock = f.get("clock", 0)
        influence = f.get("influence", 1)

        if clock >= 6:
            suggestions.append(f"{name} is ready to make a bold move against the coterie.")
        elif clock >= 3:
            suggestions.append(f"{name} is maneuvering in the shadows, tightening their grip.")
        else:
            suggestions.append(f"{name} is gathering information and testing boundaries.")

        if influence >= 5:
            suggestions.append(f"{name} can call on significant mortal or Kindred resources.")

    return suggestions
