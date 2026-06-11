
"""
Lightweight combat engine using dice_pool.
"""

from typing import Dict, Any
from .dice_pool import roll_dice_pool


def opposed_test(attacker_pool: int, defender_pool: int) -> Dict[str, Any]:
    atk = roll_dice_pool(attacker_pool)
    dfn = roll_dice_pool(defender_pool)

    net = atk["successes"] - dfn["successes"]
    outcome = "miss"
    if net > 0:
        outcome = "hit"
    elif net < 0:
        outcome = "defended"

    return {
        "attacker": atk,
        "defender": dfn,
        "net_successes": net,
        "outcome": outcome,
    }


def apply_damage(character: Dict[str, Any], net_successes: int) -> Dict[str, Any]:
    if net_successes <= 0:
        return character

    health = character.setdefault("health", {"current": 7, "max": 7})
    health["current"] = max(0, health["current"] - net_successes)
    return character
