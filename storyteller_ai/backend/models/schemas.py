from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class Character(BaseModel):
    name: str
    clan: Optional[str] = None
    notes: Optional[str] = None
    attributes: Dict[str, Any] = {}
    conditions: List[str] = []


class Scene(BaseModel):
    location: str
    tension: str = "medium"


class GameState(BaseModel):
    scene: Scene
    characters: List[Character] = []
    campaign: Dict[str, Any] = {}
