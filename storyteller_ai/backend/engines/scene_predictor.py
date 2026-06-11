"""
Scene predictor: suggests next scene directions based on tension and clocks.
"""

from typing import Dict, Any, List
from .faction_ai import suggest_faction_moves
from .secrecy_tracker import describe_secrecy


def suggest_next_scenes(state: Dict[str, Any]) -> List[str]:
    scene = state.get("scene", {})
    campaign = state.get("campaign", {})

    tension = scene.get("tension", "medium")
    faction_moves = suggest_faction_moves(campaign)
    secrecy_status = describe_secrecy(campaign)

    suggestions: List[str] = []

    if tension == "low":
        suggestions.append("Introduce a subtle complication or rumor that hints at deeper trouble.")
    elif tension == "medium":
        suggestions.append("Escalate an existing thread: a faction agent appears, or a secret is revealed.")
    else:
        suggestions.append("Push toward a confrontation or revelation that forces the coterie to choose a side.")

    suggestions.append(f"Faction undercurrents: {faction_moves[0] if faction_moves else 'No major moves yet.'}")
    suggestions.append(f"Masquerade status: {secrecy_status}")

    return suggestions
