"""
Secrecy tracker: how close things are to exposure.
"""

from typing import Dict, Any


def ensure_secrecy(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return campaign.setdefault("secrecy", {"level": 0, "notes": []})


def adjust_secrecy(campaign: Dict[str, Any], delta: int, reason: str) -> Dict[str, Any]:
    secrecy = ensure_secrecy(campaign)
    secrecy["level"] = max(0, secrecy.get("level", 0) + delta)
    secrecy["notes"].append(reason)
    return secrecy


def describe_secrecy(campaign: Dict[str, Any]) -> str:
    secrecy = ensure_secrecy(campaign)
    level = secrecy.get("level", 0)
    if level >= 8:
        status = "The Masquerade is on the brink of collapse."
    elif level >= 5:
        status = "The Masquerade is strained; hunters or authorities may be circling."
    elif level >= 2:
        status = "There have been a few close calls, but nothing catastrophic yet."
    else:
        status = "The Masquerade is currently stable."
    return status
