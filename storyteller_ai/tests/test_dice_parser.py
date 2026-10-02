import pytest

from backend.rules.dice.parser import (
    DiceExpression,
    IntTerm,
    ParseError,
    Reference,
    parse_expression,
)


@pytest.mark.parametrize(
    "expression",
    ["1d20+5", "d20", "2d20kh1+3", "8d10>=6!10", "2d6+{cool}", "4dF+2", "1d100<=45"],
)
def test_parse_supported_dice_expressions(expression):
    parsed = parse_expression(expression)

    assert parsed.terms


def test_parse_preserves_terms_and_references():
    parsed = parse_expression("2d6+{cool}-3")

    assert isinstance(parsed.terms[0], DiceExpression)
    assert parsed.terms[0].value.count == 2
    assert parsed.terms[0].value.sides == 6
    assert isinstance(parsed.terms[1], Reference)
    assert isinstance(parsed.terms[2], IntTerm)
    assert parsed.operators == ("+", "-")


@pytest.mark.parametrize("expression", ["", "101d6", "0d6", "1d1001", "2d6+", "2d6+{}"])
def test_parse_rejects_invalid_or_unbounded_expressions(expression):
    with pytest.raises(ParseError):
        parse_expression(expression)