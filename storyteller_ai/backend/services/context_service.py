from dataclasses import dataclass, field
import re
from typing import Any

from ..models.chat import Visibility
from ..models.state import Event, GameState


@dataclass
class MemoryFact:
    text: str
    subject_id: str | None = None
    importance: int = 3
    visibility: Visibility = field(default_factory=lambda: Visibility(scope="public"))


class ContextService:
    def __init__(self):
        self.memories: dict[str, list[MemoryFact]] = {}
        self.usage: dict[str, int] = {}

    def build(
        self, campaign_id: str, state: GameState, history: list[Event],
        protocol: str = "", ruleset_digest: str = "", setting_digest: str = "",
        current_input: str = "", budget: int = 12000, actor_scope: str = "gm",
    ) -> dict[str, Any]:
        layers = [
            ("protocol", protocol), ("ruleset", ruleset_digest), ("setting", setting_digest),
            ("state", repr(state.model_dump(mode="json"))),
            ("memory", self._memory_text(campaign_id, current_input, actor_scope)),
            ("recent_history", self._history_text(history)), ("input", current_input),
        ]
        remaining = budget
        rendered = []
        included = []
        for name, text in layers:
            text = text or ""
            clipped = text[:remaining]
            rendered.append(f"[{name}]\n{clipped}")
            included.append(name)
            remaining -= len(clipped)
            if remaining <= 0:
                break
        result = "\n\n".join(rendered)
        result = result[:budget]
        self.usage[campaign_id] = self.usage.get(campaign_id, 0) + len(result)
        return {"text": result, "layers": included, "characters": len(result), "budget": budget}

    def add_memory(self, campaign_id: str, fact: MemoryFact) -> None:
        self.memories.setdefault(campaign_id, []).append(fact)

    def search_memory(self, campaign_id: str, query: str, actor_scope: str = "player", limit: int = 10) -> list[MemoryFact]:
        tokens = set(re.findall(r"\w+", query.lower()))
        results = []
        for fact in self.memories.get(campaign_id, []):
            if fact.visibility.scope == "gm_only" and actor_scope != "gm":
                continue
            score = len(tokens.intersection(re.findall(r"\w+", fact.text.lower())))
            if score:
                results.append((score, fact))
        results.sort(key=lambda item: (item[0], item[1].importance), reverse=True)
        return [fact for _, fact in results[:limit]]

    def usage_report(self, campaign_id: str) -> dict[str, int]:
        return {"characters": self.usage.get(campaign_id, 0)}

    @staticmethod
    def summarize(history: list[Event], level: str = "session") -> dict[str, Any]:
        if not history:
            return {"level": level, "text": "", "covers_from_seq": 0, "covers_to_seq": 0}
        return {
            "level": level,
            "text": " ".join(event.type for event in history),
            "covers_from_seq": history[0].seq,
            "covers_to_seq": history[-1].seq,
        }

    @staticmethod
    def _history_text(history: list[Event]) -> str:
        return "\n".join(f"{event.seq}: {event.type}" for event in history[-20:])

    def _memory_text(self, campaign_id: str, query: str, actor_scope: str) -> str:
        return "\n".join(fact.text for fact in self.search_memory(campaign_id, query, actor_scope, limit=10))


context_service = ContextService()