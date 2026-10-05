from ..models.state import Event, GameState, Scene, Tracker, TurnOrder


def apply_event(state: GameState, event: Event) -> GameState:
    updated = state.model_copy(deep=True)
    updated.head_seq = event.seq
    if event.type == "scene.started" or event.type == "scene.updated":
        updated.scene = Scene.model_validate(event.payload["scene"])
    elif event.type == "scene.ended":
        updated.scene = None
    elif event.type == "session.started":
        updated.session_id = event.payload["id"]
    elif event.type == "session.ended":
        updated.session_id = None
    elif event.type == "campaign.configured":
        updated.flags["campaign_status"] = event.payload["campaign"]["status"]
    elif event.type == "turn.started":
        updated.turn_number += 1
    elif event.type == "turn_order.changed":
        updated.turn_order = TurnOrder.model_validate(event.payload["turn_order"])
    elif event.type == "tracker.changed":
        tracker = Tracker.model_validate(event.payload["tracker"])
        updated.trackers[tracker.id] = tracker
    elif event.type == "dice.rolled":
        roll = event.payload.get("roll", {})
        proof = roll.get("rng", {}) if isinstance(roll, dict) else {}
        updated.rng_counter = event.payload.get(
            "counter_end", proof.get("counter_end", updated.rng_counter),
        )
    elif event.type == "game_state.updated":
        updated.storyteller_state = _merge_patch(
            updated.storyteller_state, event.payload.get("patch", {}),
        )
    return updated


def _merge_patch(current: dict, patch: dict) -> dict:
    merged = {**current}
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_patch(merged[key], value)
        else:
            merged[key] = value
    return merged


def replay(campaign_id: str, branch_id: str, events: list[Event]) -> GameState:
    state = GameState(campaign_id=campaign_id, branch_id=branch_id)
    for event in events:
        state = apply_event(state, event)
    return state