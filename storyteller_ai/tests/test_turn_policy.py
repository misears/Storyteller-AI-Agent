from datetime import datetime, timedelta, timezone

from backend.models.campaign import TurnPolicy
from backend.services.turn_policy import TurnCoordinator, derive_mode, spotlight_guidance


def test_turn_policy_batches_resolves_and_guides_spotlight():
    coordinator = TurnCoordinator(
        TurnPolicy(mode="freeform", declare_window_seconds=10),
        present_character_ids={"a", "b"},
        opened_at=datetime.now(timezone.utc) - timedelta(seconds=11),
    )

    assert coordinator.declare("a", "Act") == "batched"
    assert coordinator.declare("b", "React") == "resolved"
    assert coordinator.timed_out()
    assert derive_mode(1) == "solo"
    assert derive_mode(3) == "group"
    assert spotlight_guidance({"a": 1, "b": 4, "c": 2}) == ["b", "c"]