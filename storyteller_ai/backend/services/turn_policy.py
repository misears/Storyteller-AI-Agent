from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..models.campaign import TurnPolicy


@dataclass
class TurnCoordinator:
    policy: TurnPolicy
    present_character_ids: set[str] = field(default_factory=set)
    declarations: dict[str, str] = field(default_factory=dict)
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def declare(self, character_id: str, content: str) -> str:
        if self.policy.mode == "round_robin" and self.declarations and character_id not in self.declarations:
            return "queued"
        self.declarations[character_id] = content
        if self.policy.resolve_when_all_declared and self.present_character_ids.issubset(self.declarations):
            return "resolved"
        return "batched"

    def timed_out(self, now: datetime | None = None) -> bool:
        if self.policy.declare_window_seconds <= 0:
            return False
        return (now or datetime.now(timezone.utc)) - self.opened_at >= timedelta(seconds=self.policy.declare_window_seconds)


def derive_mode(active_players: int) -> str:
    if active_players <= 1:
        return "solo"
    return "group"


def spotlight_guidance(debt: dict[str, int], limit: int = 2) -> list[str]:
    return [character_id for character_id, _ in sorted(debt.items(), key=lambda item: item[1], reverse=True)[:limit]]