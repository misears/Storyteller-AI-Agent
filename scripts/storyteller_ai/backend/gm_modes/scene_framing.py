from typing import Dict, Any


def build_scene_summary(state: Dict[str, Any]) -> str:
    scene = state.get("scene", {})
    location = scene.get("location", "an unspecified location")
    tension = scene.get("tension", "unknown")
    return f"Current scene is at {location}, with tension level: {tension}."
