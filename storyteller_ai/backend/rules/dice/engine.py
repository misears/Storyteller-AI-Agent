"""Server-authoritative dice expression evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mechanics import bands, pool_successes, roll_under, sum_vs_target
from .parser import DiceExpression, DiceModifier, IntTerm, Reference, parse_expression
from .rng import CounterRNG


@dataclass(frozen=True)
class EvaluatedRoll:
    dice: list[dict[str, Any]]
    total: int | None
    successes: int | None
    outcome: str | None
    counter_start: int
    counter_end: int
    interpretation: str


def _resolve(value: int | Reference, references: dict[str, int]) -> int:
    if isinstance(value, Reference):
        if value.name not in references:
            raise ValueError(f"unresolved dice reference: {{{value.name}}}")
        value = references[value.name]
    if not isinstance(value, int):
        raise ValueError("dice references must resolve to integers")
    return value


def _modifier(term: DiceExpression, kind: str) -> DiceModifier | None:
    return next((item for item in term.value.modifiers if item.kind == kind), None)


def evaluate(
    expression: str, seed: bytes | str, branch_id: str, counter: int = 0,
    references: dict[str, int] | None = None, mechanic: str = "sum_vs_target",
    target: int | None = None, params: dict[str, Any] | None = None,
) -> EvaluatedRoll:
    parsed = parse_expression(expression)
    references = references or {}
    params = params or {}
    rng = CounterRNG(seed, branch_id, counter)
    dice_results: list[dict[str, Any]] = []
    term_values: list[int] = []
    successes: int | None = None

    for item in parsed.terms:
        if isinstance(item, IntTerm):
            term_values.append(item.value)
            continue
        if isinstance(item, Reference):
            term_values.append(_resolve(item, references))
            continue
        term = item.value
        count = _resolve(term.count, references)
        if count < 1 or count > 100:
            raise ValueError("dice count must be between 1 and 100")
        sides = 3 if term.sides == "F" else 100 if term.sides == "%" else term.sides
        raw_values: list[int] = []
        explode = _modifier(item, "explode")
        threshold = explode.value if explode and explode.value is not None else sides
        pending = count
        explosions = [0] * count
        while pending:
            pending -= 1
            index = len(raw_values)
            value = rng.draw(sides)
            raw_values.append(value)
            dice_results.append({"sides": sides, "value": value, "kept": True, "exploded": False})
            source_index = min(index, count - 1)
            if explode and value >= threshold and explosions[source_index] < 50:
                explosions[source_index] += 1
                pending += 1
                dice_results[-1]["exploded"] = True
        keep = _modifier(item, "kh") or _modifier(item, "kl")
        drop = _modifier(item, "dh") or _modifier(item, "dl")
        kept_values = raw_values
        if keep:
            selected = sorted(range(len(raw_values)), key=raw_values.__getitem__, reverse=keep.kind == "kh")[:keep.value]
            kept_values = [raw_values[index] for index in selected]
            for index, result in enumerate(dice_results[-len(raw_values):]):
                result["kept"] = index in selected
        if drop:
            selected = sorted(range(len(raw_values)), key=raw_values.__getitem__, reverse=drop.kind == "dh")[:drop.value]
            kept_values = [value for index, value in enumerate(raw_values) if index not in selected]
            for index, result in enumerate(dice_results[-len(raw_values):]):
                if index in selected:
                    result["kept"] = False
        reroll = _modifier(item, "reroll")
        if reroll:
            rerolled = []
            for value in kept_values:
                compare = reroll.comparator or "="
                matches = {"=": value == reroll.value, ">": value > reroll.value, "<": value < reroll.value,
                           ">=": value >= reroll.value, "<=": value <= reroll.value}[compare]
                rerolled.append(rng.draw(sides) if matches else value)
            kept_values = rerolled
        term_values.append(sum(kept_values))
        success_modifier = _modifier(item, "successes")
        if success_modifier:
            difficulty = _resolve(success_modifier.value, references)
            successes = sum(value >= difficulty for value in kept_values)
            failure_modifier = _modifier(item, "failures")
            if failure_modifier:
                successes -= sum(value <= failure_modifier.value for value in kept_values)

    total = term_values[0] if len(term_values) == 1 else sum(
        value if operator == "+" else -value
        for value, operator in zip(term_values[1:], parsed.operators)
    ) + term_values[0]
    outcome: str | None
    if mechanic == "pool_successes":
        pool = pool_successes(
            [item["value"] for item in dice_results],
            target or params.get("difficulty", 6), params.get("ones_cancel", False),
            params.get("botch_on_net_ones", True), params.get("explode"),
        )
        successes, outcome = pool["successes"], pool["outcome"]
    elif mechanic == "bands":
        outcome = bands(total, params.get("bands", []))
    elif mechanic == "roll_under":
        outcome = roll_under(total, target, params)
    else:
        outcome = sum_vs_target(total, target, params) if target is not None else None
    return EvaluatedRoll(dice_results, total, successes, outcome, counter, rng.counter, f"{mechanic}: {expression}")