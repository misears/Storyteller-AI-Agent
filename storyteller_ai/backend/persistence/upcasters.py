from collections.abc import Callable
from typing import Any


class EventUpcaster:
    def __init__(self):
        self._upcasters: dict[tuple[str, int], Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(self, event_type: str, from_version: int, transform: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._upcasters[(event_type, from_version)] = transform

    def upcast(self, event_type: str, payload: dict[str, Any], version: int, target_version: int) -> tuple[dict[str, Any], int]:
        while version < target_version:
            transform = self._upcasters.get((event_type, version))
            if transform is None:
                raise ValueError(f"no upcaster for {event_type} v{version}")
            payload = transform(payload)
            version += 1
        return payload, version