"""
NPC memory: lightweight note store keyed by name.
"""

from typing import Dict, Any, List


def ensure_npc_store(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return campaign.setdefault("npc_memory", {})


def remember_npc(campaign: Dict[str, Any], name: str, note: str) -> None:
    store = ensure_npc_store(campaign)
    notes: List[str] = store.setdefault(name, [])
    notes.append(note)


def summarize_npc(campaign: Dict[str, Any], name: str) -> str:
    store = ensure_npc_store(campaign)
    notes = store.get(name, [])
    if not notes:
        return f"No known details about {name} yet."
    return f"{name}: " + " ".join(notes)
