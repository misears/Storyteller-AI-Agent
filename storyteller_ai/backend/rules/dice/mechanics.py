"""Ruleset-independent outcome interpreters."""

from __future__ import annotations

from typing import Any


def sum_vs_target(total: int, target: int | None, params: dict[str, Any] | None = None) -> str:
    params = params or {}
    if params.get("critical_on_natural") and total == params["critical_on_natural"]:
        return "critical_success"
    if params.get("failure_on_natural") and total == params["failure_on_natural"]:
        return "critical_failure"
    return "success" if target is not None and total >= target else "failure"


def pool_successes(
    values: list[int], difficulty: int = 6, ones_cancel: bool = False,
    botch_on_net_ones: bool = True, explode: int | None = None,
) -> dict[str, Any]:
    successes = sum(value >= difficulty for value in values)
    ones = sum(value == 1 for value in values)
    net_successes = max(0, successes - ones) if ones_cancel else successes
    botch = botch_on_net_ones and net_successes == 0 and ones > 0
    return {
        "successes": net_successes,
        "ones": ones,
        "botch": botch,
        "outcome": "botch" if botch else ("success" if net_successes else "failure"),
        "explode": explode,
    }


def bands(total: int, definitions: list[dict[str, Any]]) -> str:
    for definition in definitions:
        if ("min" not in definition or total >= definition["min"]) and (
            "max" not in definition or total <= definition["max"]
        ):
            return definition["outcome"]
    return "failure"


def roll_under(total: int, target: int | None, params: dict[str, Any] | None = None) -> str:
    params = params or {}
    if target is None:
        return "failure"
    if total <= params.get("critical_success_at", -1):
        return "critical_success"
    if total >= params.get("critical_failure_at", 10**9):
        return "critical_failure"
    return "success" if total <= target else "failure"