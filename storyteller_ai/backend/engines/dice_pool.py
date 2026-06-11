"""
Dice pool engine for Storyteller-style systems.
Supports successes on 8+ with 10-again.
"""

import random
from typing import List, Dict, Any


def roll_dice_pool(pool: int, again: int = 10) -> Dict[str, Any]:
    if pool <= 0:
        return {"dice": [], "successes": 0, "botch": True}

    rolls: List[int] = []
    to_roll = pool

    while to_roll > 0:
        die = random.randint(1, 10)
        rolls.append(die)
        if die >= again:
            to_roll += 1  # explode
        to_roll -= 1

    successes = sum(1 for r in rolls if r >= 8)
    botch = successes == 0 and any(r == 1 for r in rolls)

    return {
        "dice": rolls,
        "successes": successes,
        "botch": botch,
    }
