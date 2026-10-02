from backend.engines.trackers import adjust_tracker, tracker_progress, tracker_status
from backend.models.state import Tracker


def test_generic_tracker_behavior_is_bounded():
    tracker = Tracker(id="doom", label="Doom", kind="clock", max=8, value=7)

    full = adjust_tracker(tracker, 4)
    empty = adjust_tracker(tracker, -20)

    assert tracker.value == 7
    assert full.value == 8
    assert tracker_status(full) == "full"
    assert empty.value == 0
    assert tracker_status(empty) == "empty"
    assert tracker_progress(tracker) == 7 / 8