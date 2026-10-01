import pytest

from backend.rules.formulas import FormulaError, evaluate_formula


def test_formula_evaluator_supports_ruleset_operations():
    values = {"strength": 8, "stamina": 3}

    assert evaluate_formula("strength + stamina * 2", values) == 14
    assert evaluate_formula("max(1, stamina) + floor(3.9)", values) == 6
    assert evaluate_formula("mod(strength)", values) == -1
    assert evaluate_formula("strength >= 5", values) is True


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "strength.__class__",
        "(lambda x: x)(strength)",
        "eval('strength')",
        "strength / 2",
        "unknown + 1",
    ],
)
def test_formula_evaluator_rejects_unsafe_or_unknown_expressions(expression):
    with pytest.raises(FormulaError):
        evaluate_formula(expression, {"strength": 8})


def test_formula_helpers_are_explicitly_allow_listed():
    assert evaluate_formula("double(strength)", {"strength": 4}, {"double": lambda value: value * 2}) == 8
    with pytest.raises(FormulaError):
        evaluate_formula("double(strength)", {"strength": 4})