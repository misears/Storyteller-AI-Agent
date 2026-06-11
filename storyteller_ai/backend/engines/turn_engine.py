"""
Turn engine: tracks beats / turns in the chronicle.
"""

from typing import Dict, Any


def ensure_turns(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return campaign.setdefault("turns", {"beat": 0, "session": 1})


def advance_beat(campaign: Dict[str, Any], amount: int = 1) -> Dict[str, Any]:
    turns = ensure_turns(campaign)
    turns["beat"] = max(0, turns.get("beat", 0) + amount)
    return turns


def new_session(campaign: Dict[str, Any]) -> Dict[str, Any]:
    turns = ensure_turns(campaign)
    turns["session"] = turns.get("session", 1) + 1
    turns["beat"] = 0
    return turns
