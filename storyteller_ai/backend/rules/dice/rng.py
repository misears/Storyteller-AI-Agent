"""Deterministic, auditable counter-based random number generation."""

from __future__ import annotations

import hashlib
import hmac


ALGORITHM = "hmac-sha256-ctr-v1"


class CounterRNG:
    def __init__(self, seed: bytes | str, branch_id: str, counter: int = 0):
        seed_bytes = seed.encode() if isinstance(seed, str) else seed
        self._key = hmac.new(seed_bytes, branch_id.encode(), hashlib.sha256).digest()
        self.counter = counter

    def draw(self, sides: int) -> int:
        if sides < 1:
            raise ValueError("sides must be positive")
        modulus = 1 << 256
        limit = modulus - modulus % sides
        while True:
            digest = hmac.new(
                self._key, self.counter.to_bytes(8, "big"), hashlib.sha256
            ).digest()
            self.counter += 1
            value = int.from_bytes(digest, "big")
            if value < limit:
                return value % sides + 1


def verify_draws(
    seed: bytes | str, branch_id: str, counter_start: int, sides: list[int]
) -> tuple[list[int], int]:
    rng = CounterRNG(seed, branch_id, counter_start)
    values = [rng.draw(sides_value) for sides_value in sides]
    return values, rng.counter