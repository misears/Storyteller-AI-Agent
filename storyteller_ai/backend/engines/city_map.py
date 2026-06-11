"""
City map: simple district + tag model.
"""

from typing import Dict, Any, List


def ensure_city(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return campaign.setdefault("city", {"districts": []})


def add_district(campaign: Dict[str, Any], name: str, tags: List[str] | None = None) -> Dict[str, Any]:
    city = ensure_city(campaign)
    districts = city["districts"]
    for d in districts:
        if d.get("name") == name:
            return d
    district = {"name": name, "tags": tags or []}
    districts.append(district)
    return district


def describe_districts(campaign: Dict[str, Any]) -> List[str]:
    city = ensure_city(campaign)
    out: List[str] = []
    for d in city["districts"]:
        tags = ", ".join(d.get("tags", [])) or "no notable tags"
        out.append(f"{d.get('name')}: {tags}")
    return out
