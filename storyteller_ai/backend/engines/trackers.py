"""Generic clock and meter behavior for setting-pack trackers."""

from ..models.state import Tracker


def adjust_tracker(tracker: Tracker, delta: int) -> Tracker:
    tracker = tracker.model_copy(deep=True)
    tracker.value = max(0, min(tracker.max, tracker.value + delta))
    return tracker


def tracker_status(tracker: Tracker) -> str:
    if tracker.value >= tracker.max:
        return "full"
    if tracker.value <= 0:
        return "empty"
    return "active"


def tracker_progress(tracker: Tracker) -> float:
    return tracker.value / tracker.max if tracker.max else 0.0