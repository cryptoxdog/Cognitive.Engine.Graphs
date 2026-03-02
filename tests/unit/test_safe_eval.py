# tests/test_safe_eval.py
"""
Tests for engine.utils.safe_eval — AST-whitelist expression evaluator.

Covers:
- Arithmetic operators: +, -, *, /, //, %, **
- Unary operators: -x, +x
- Whitelisted functions: abs, min, max, round, log, exp, sqrt
- Variable substitution from context
- Rejection of: string constants, imports, attribute access,
  list comprehensions, lambda, exec, eval, __builtins__
"""

from __future__ import annotations

import math

import pytest

from engine.utils.safe_eval import safe_eval

# ── Arithmetic Operators ──────────────────────────────────


class TestArithmetic:
    def test_addition(self):
        assert safe_eval("x + y", {"x": 3, "y": 7}) == 10

    def test_subtraction(self):
        assert safe_eval("x - y", {"x": 10, "y": 4}) == 6

    def test_multiplication(self):
        assert safe_eval("x * y", {"x": 5, "y": 6}) == 30

    def test_true_division(self):
        assert safe_eval("x / y", {"x": 7, "y": 2}) == pytest.approx(3.5)

    def test_floor_division(self):
        assert safe_eval("x // y", {"x": 7, "y": 2}) == 3

    def test_modulo(self):
        assert safe_eval("x % y", {"x": 10, "y": 3}) == 1

    def test_power(self):
        assert safe_eval("x ** y", {"x": 2, "y": 10}) == 1024

    def test_compound_expression(self):
        result = safe_eval("(a + b) * c - d / e", {"a": 1, "b": 2, "c": 3, "d": 4, "e": 2})
        assert result == pytest.approx(7.0)

    def test_numeric_literal(self):
        assert safe_eval("x + 100", {"x": 5}) == 105

    def test_float_literal(self):
        assert safe_eval("x / 12.0", {"x": 120000}) == pytest.approx(10000.0)

    def test_division_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            safe_eval("x / 0", {"x": 1})


# ── Unary Operators ───────────────────────────────────────


class TestUnary:
    def test_negation(self):
        assert safe_eval("-x", {"x": 42}) == -42

    def test_positive(self):
        assert safe_eval("+x", {"x": 42}) == 42

    def test_double_negation(self):
        assert safe_eval("-(-x)", {"x": 5}) == 5


# ── Whitelisted Functions ─────────────────────────────────


class TestFunctions:
    def test_abs(self):
        assert safe_eval("abs(x)", {"x": -7}) == 7

    def test_min(self):
        assert safe_eval("min(a, b)", {"a": 3, "b": 9}) == 3

    def test_max(self):
        assert safe_eval("max(a, b)", {"a": 3, "b": 9}) == 9

    def test_round(self):
        assert safe_eval("round(x)", {"x": 3.7}) == 4

    def test_log(self):
        assert safe_eval("log(x)", {"x": math.e}) == pytest.approx(1.0)

    def test_exp(self):
        assert safe_eval("exp(x)", {"x": 0}) == pytest.approx(1.0)

    def test_sqrt(self):
        assert safe_eval("sqrt(x)", {"x": 144}) == pytest.approx(12.0)

    def test_nested_function_call(self):
        assert safe_eval("abs(min(a, b))", {"a": -5, "b": -10}) == 10

    def test_function_in_expression(self):
        result = safe_eval("sqrt(x) + abs(y)", {"x": 9, "y": -4})
        assert result == pytest.approx(7.0)


# ── Variable Context ──────────────────────────────────────


class TestContext:
    def test_unknown_variable_raises(self):
        with pytest.raises(ValueError, match="Unknown variable"):
            safe_eval("missing + 1", {"x": 1})

    def test_context_isolation(self):
        ctx = {"a": 10, "b": 20}
        safe_eval("a + b", ctx)
        assert ctx == {"a": 10, "b": 20}  # unchanged

    def test_zero_value_variable(self):
        assert safe_eval("x + 1", {"x": 0}) == 1

    def test_negative_value_variable(self):
        assert safe_eval("x * 2", {"x": -3}) == -6

    def test_float_context(self):
        assert safe_eval("density * 1000", {"density": 0.95}) == pytest.approx(950.0)


# ── Security: Rejected Patterns ───────────────────────────


class TestSecurityRejections:
    def test_string_constant_rejected(self):
        with pytest.raises(ValueError, match="Only numeric constants"):
            safe_eval("'hello'", {})

    def test_import_rejected(self):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval("__import__('os')", {})

    def test_attribute_access_rejected(self):
        with pytest.raises(ValueError, match="Disallowed expression node"):
            safe_eval("x.__class__", {"x": 1})

    def test_subscript_rejected(self):
        with pytest.raises(ValueError, match="Disallowed expression node"):
            safe_eval("x[0]", {"x": [1, 2, 3]})

    def test_lambda_rejected(self):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval("(lambda: 1)()", {})

    def test_list_comprehension_rejected(self):
        with pytest.raises(ValueError, match="Disallowed expression node"):
            safe_eval("[x for x in range(10)]", {})

    def test_non_whitelisted_function_rejected(self):
        with pytest.raises(ValueError):
            safe_eval("eval('1+1')", {})

    def test_exec_rejected(self):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval("exec('x=1')", {})

    def test_dunder_access_rejected(self):
        with pytest.raises(ValueError):
            safe_eval("x.__class__.__bases__", {"x": 1})

    def test_boolean_literal_treated_as_numeric(self):
        # In Python, bool is a subclass of int (True=1, False=0)
        # safe_eval allows this since booleans are numeric
        assert safe_eval("True", {}) == 1
        assert safe_eval("False", {}) == 0
        assert safe_eval("True + 1", {}) == 2

    def test_walrus_operator_rejected(self):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval("(x := 5)", {})


# ── Real-world Derived Parameter Expressions ──────────────


class TestDomainExpressions:
    """Expressions that appear in actual PlasticOS domain spec derived_parameters."""

    def test_annual_to_monthly_income(self):
        result = safe_eval("annualincomeusd / 12.0", {"annualincomeusd": 60000})
        assert result == pytest.approx(5000.0)

    def test_density_midpoint(self):
        result = safe_eval("(min_density + max_density) / 2", {"min_density": 0.90, "max_density": 0.97})
        assert result == pytest.approx(0.935)

    def test_mfi_range_width(self):
        result = safe_eval("max_mfi - min_mfi", {"min_mfi": 2.0, "max_mfi": 25.0})
        assert result == pytest.approx(23.0)

    def test_contamination_ppm(self):
        result = safe_eval("contamination_tolerance * 1000000", {"contamination_tolerance": 0.03})
        assert result == pytest.approx(30000.0)

    def test_volume_kg_to_lbs(self):
        result = safe_eval("volume_kg * 2.20462", {"volume_kg": 5000})
        assert result == pytest.approx(11023.1)

    def test_price_margin(self):
        result = safe_eval("(sell_price - buy_price) / sell_price", {"sell_price": 100, "buy_price": 75})
        assert result == pytest.approx(0.25)
