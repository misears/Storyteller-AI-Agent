"""Bounded parser for the campaign dice-expression grammar."""

from __future__ import annotations

from dataclasses import dataclass
import re


MAX_DICE_PER_TERM = 100
MAX_SIDES = 1000
MAX_EXPLOSIONS_PER_DIE = 50


class ParseError(ValueError):
    """Raised when a dice expression is invalid or exceeds parser limits."""


@dataclass(frozen=True)
class Reference:
    name: str


@dataclass(frozen=True)
class IntTerm:
    value: int


@dataclass(frozen=True)
class DiceModifier:
    kind: str
    value: int | None = None
    comparator: str | None = None


@dataclass(frozen=True)
class DiceTerm:
    count: int | Reference
    sides: int | str
    modifiers: tuple[DiceModifier, ...] = ()


@dataclass(frozen=True)
class DiceExpression:
    value: DiceTerm


@dataclass(frozen=True)
class Expression:
    terms: tuple[DiceExpression | IntTerm | Reference, ...]
    operators: tuple[str, ...] = ()


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


class _Parser:
    def __init__(self, source: str):
        self.source = source
        self.position = 0

    def parse(self) -> Expression:
        terms = [self._parse_term()]
        operators: list[str] = []
        while True:
            self._skip_space()
            if not self._peek() or self._peek() not in "+-":
                break
            operators.append(self._take())
            terms.append(self._parse_term())
        self._skip_space()
        if self.position != len(self.source):
            self._error("unexpected input")
        return Expression(tuple(terms), tuple(operators))

    def _parse_term(self) -> DiceExpression | IntTerm | Reference:
        self._skip_space()
        start = self.position
        value: int | Reference
        if self._peek().lower() == "d":
            value = 1
        elif self._peek() == "{":
            value = self._parse_reference()
        else:
            value = self._parse_int()

        self._skip_space()
        if self._peek().lower() != "d":
            if isinstance(value, Reference):
                return value
            return IntTerm(value)

        self.position += 1
        sides = self._parse_sides()
        modifiers = self._parse_modifiers()
        if isinstance(value, int) and not 1 <= value <= MAX_DICE_PER_TERM:
            self._error(f"dice count cannot exceed {MAX_DICE_PER_TERM}", start)
        return DiceExpression(DiceTerm(value, sides, tuple(modifiers)))

    def _parse_sides(self) -> int | str:
        self._skip_space()
        char = self._peek()
        if char.upper() in {"F", "%"}:
            self.position += 1
            return char.upper()
        sides = self._parse_int()
        if sides < 1 or sides > MAX_SIDES:
            self._error(f"sides must be between 1 and {MAX_SIDES}")
        return sides

    def _parse_modifiers(self) -> list[DiceModifier]:
        modifiers: list[DiceModifier] = []
        while True:
            self._skip_space()
            if self.source[self.position:self.position + 2] in {">=", "<="}:
                comparator = self.source[self.position:self.position + 2]
                self.position += 2
                modifiers.append(DiceModifier("successes", self._parse_number(), comparator))
            elif self._peek() and self._peek() in "><":
                comparator = self._take()
                modifiers.append(DiceModifier("successes", self._parse_number(), comparator))
            elif self._peek() == "!":
                self.position += 1
                self._skip_space()
                value = self._parse_int() if self._peek().isdigit() else None
                if value is not None and value > MAX_SIDES:
                    self._error(f"explosion threshold cannot exceed {MAX_SIDES}")
                modifiers.append(DiceModifier("explode", value))
            else:
                kind = self.source[self.position:self.position + 2].lower()
                if kind in {"kh", "kl", "dh", "dl"}:
                    self.position += 2
                    value = self._parse_int()
                    if value < 1 or value > MAX_DICE_PER_TERM:
                        self._error(f"keep/drop count must be between 1 and {MAX_DICE_PER_TERM}")
                    modifiers.append(DiceModifier(kind, value))
                elif self._peek().lower() == "r":
                    self.position += 1
                    self._skip_space()
                    comparator = "="
                    if self.source[self.position:self.position + 2] in {">=", "<="}:
                        comparator = self.source[self.position:self.position + 2]
                        self.position += 2
                    elif self._peek() and self._peek() in ">=<":
                        comparator = self._take()
                    modifiers.append(DiceModifier("reroll", self._parse_int(), comparator))
                elif self._peek().lower() == "f":
                    self.position += 1
                    modifiers.append(DiceModifier("failures", self._parse_int()))
                else:
                    break
        return modifiers

    def _parse_number(self) -> int | Reference:
        self._skip_space()
        if self._peek() == "{":
            return self._parse_reference()
        return self._parse_int()

    def _parse_reference(self) -> Reference:
        self.position += 1
        match = _IDENTIFIER.match(self.source, self.position)
        if not match:
            self._error("reference must contain an identifier")
        self.position = match.end()
        if self._peek() != "}":
            self._error("reference must end with '}'")
        self.position += 1
        return Reference(match.group())

    def _parse_int(self) -> int:
        self._skip_space()
        start = self.position
        while self._peek().isdigit():
            self.position += 1
        if start == self.position:
            self._error("expected an integer")
        return int(self.source[start:self.position])

    def _skip_space(self) -> None:
        while self._peek().isspace():
            self.position += 1

    def _peek(self) -> str:
        return self.source[self.position] if self.position < len(self.source) else ""

    def _take(self) -> str:
        char = self._peek()
        self.position += 1
        return char

    def _error(self, message: str, position: int | None = None) -> None:
        raise ParseError(f"{message} at position {self.position if position is None else position}")


def parse_expression(source: str) -> Expression:
    """Parse a bounded dice expression without evaluating or executing it."""
    if not isinstance(source, str) or not source.strip():
        raise ParseError("expression must not be empty")
    return _Parser(source).parse()