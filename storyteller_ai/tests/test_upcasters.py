from backend.persistence.upcasters import EventUpcaster


def test_event_upcaster_advances_versions():
    upcaster = EventUpcaster()
    upcaster.register("scene.started", 1, lambda payload: {**payload, "migrated": True})

    payload, version = upcaster.upcast("scene.started", {"id": "scene"}, 1, 2)

    assert payload["migrated"] is True
    assert version == 2