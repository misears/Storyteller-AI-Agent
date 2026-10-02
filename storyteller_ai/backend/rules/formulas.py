"""AST-allow-listed evaluator for ruleset formulas."""

from __future__ import annotations

import ast
import math
from numbers import Real
from typing import Callable, Mapping


class FormulaError(ValueError):
    """Raised when a formula is invalid or uses a disallowed operation."""


MAX_NODES = 100
_FUNCTIONS: dict[str, Callable[..., Real]] = {
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "mod": lambda value: (value - 10) // 2,
}
_BINOPS: dict[type[ast.operator], Callable[[Real, Real], Real]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
}
_CMPOPS: dict[type[ast.cmpop], Callable[[Real, Real], bool]] = {
    ast.Eq: lambda left, right: left == right,
    ast.NotEq: lambda left, right: left != right,
    ast.Lt: lambda left, right: left < right,
    ast.LtE: lambda left, right: left <= right,
    ast.Gt: lambda left, right: left > right,
    ast.GtE: lambda left, right: left >= right,
}


def evaluate_formula(
    expression: str, values: Mapping[str, Real],
    helpers: Mapping[str, Callable[..., Real]] | None = None,
) -> Real | bool:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"invalid formula: {exc.msg}") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise FormulaError(f"formula exceeds the {MAX_NODES}-node limit")
    functions = {**_FUNCTIONS, **(helpers or {})}
    return _evaluate(tree.body, values, functions)


def _evaluate(
    node: ast.AST, values: Mapping[str, Real],
    functions: Mapping[str, Callable[..., Real]],
) -> Real | bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        value = values.get(node.id)
        if not isinstance(value, Real) or isinstance(value, bool):
            raise FormulaError(f"unknown or non-numeric name: {node.id}")
        return value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, values, functions)
        if isinstance(value, bool):
            raise FormulaError("boolean cannot be used in arithmetic")
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _evaluate(node.left, values, functions)
        right = _evaluate(node.right, values, functions)
        if isinstance(left, bool) or isinstance(right, bool):
            raise FormulaError("boolean cannot be used in arithmetic")
        try:
            return _BINOPS[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise FormulaError("division by zero") from exc
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, values, functions)
        for operator, comparator in zip(node.ops, node.comparators):
            if type(operator) not in _CMPOPS:
                raise FormulaError(f"comparison is not allowed: {type(operator).__name__}")
            right = _evaluate(comparator, values, functions)
            if not _CMPOPS[type(operator)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = functions.get(node.func.id)
        if function is None or node.keywords:
            raise FormulaError(f"function is not allowed: {ast.unparse(node.func)}")
        args = [_evaluate(argument, values, functions) for argument in node.args]
        if any(isinstance(argument, bool) for argument in args):
            raise FormulaError("boolean cannot be passed to a formula function")
        try:
            return function(*args)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise FormulaError(f"invalid arguments for {node.func.id}") from exc
    raise FormulaError(f"expression is not allowed: {ast.unparse(node)}")