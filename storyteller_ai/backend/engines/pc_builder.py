"""
PC builder: creates simple character dicts.
"""

from typing import Dict, Any


def create_pc(name: str, clan: str | None = None) -> Dict[str, Any]:
    return {
        "name": name,
        "clan": clan,
        "attributes": {
            "physical": {"strength": 2, "dexterity": 2, "stamina": 2},
            "social": {"charisma": 2, "manipulation": 2, "composure": 2},
            "mental": {"intelligence": 2, "wits": 2, "resolve": 2},
        },
        "skills": {},
        "conditions": [],
        "health": {"current": 7, "max": 7},
        "willpower": {"current": 5, "max": 5},
    }
