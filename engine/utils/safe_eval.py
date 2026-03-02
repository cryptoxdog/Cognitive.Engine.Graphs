"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [utils, safe-eval]
owner: engine-team
status: active
--- /L9_META ---

engine/utils/safe_eval.py
AST-whitelist expression evaluator. Replaces eval() for derived parameters
and unit conversion formulas.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from typing import Any

_SAFE_BINARY_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "log": math.log,
    "exp": math.exp,
    "sqrt": math.sqrt,
}


def safe_eval(expression: str, context: dict[str, Any]) -> Any:
    """
    Evaluate a simple algebraic expression with variable substitution.
    Only allows arithmetic operations, numeric literals, and whitelisted functions.

    Raises ValueError on disallowed AST node types.
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f"Only numeric constants allowed, got {type(node.value).__name__}")
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCS:
            return _SAFE_FUNCS[node.id]
        if node.id not in ctx:
            raise ValueError(f"Unknown variable: {node.id!r}")
        return ctx[node.id]
    if isinstance(node, ast.BinOp):
        bin_op_type = type(node.op)
        if bin_op_type not in _SAFE_BINARY_OPS:
            raise ValueError(f"Unsupported operator: {bin_op_type.__name__}")
        bin_op_func = _SAFE_BINARY_OPS[bin_op_type]
        return bin_op_func(_eval_node(node.left, ctx), _eval_node(node.right, ctx))
    if isinstance(node, ast.UnaryOp):
        unary_op_type = type(node.op)
        if unary_op_type not in _SAFE_UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {unary_op_type.__name__}")
        unary_op_func = _SAFE_UNARY_OPS[unary_op_type]
        return unary_op_func(_eval_node(node.operand, ctx))
    if isinstance(node, ast.Call):
        func = _eval_node(node.func, ctx)
        if func not in _SAFE_FUNCS.values():
            raise ValueError(f"Function not whitelisted: {ast.dump(node.func)}")
        args = [_eval_node(a, ctx) for a in node.args]
        return func(*args)
    raise ValueError(f"Disallowed expression node: {type(node).__name__}")
