"""
--- L9_META ---
l9_schema: 1
origin: gap-fix
engine: graph
layer: [inference]
tags: [inference, rules, registry, plastics]
owner: engine-team
status: active
--- /L9_META ---

engine/inference_rule_registry.py

GAP-3 FIX: Active inference functions for the plastics domain.
Replaces the empty registry with 6 production rules.
All rules are pure functions — no I/O, no side effects.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class InferenceContext:
    tenant_id: str
    domain_id: str
    pass_number: int = 1


@dataclasses.dataclass(frozen=True)
class InferenceResult:
    value: Any
    confidence: float
    rule: str


# ── Rule registry ──────────────────────────────────────────────────────────────

RuleFn = Callable[[dict[str, Any], InferenceContext], InferenceResult | None]
_REGISTRY: dict[str, RuleFn] = {}


def _register(name: str) -> Callable[[RuleFn], RuleFn]:
    def decorator(fn: RuleFn) -> RuleFn:
        _REGISTRY[name] = fn
        return fn
    return decorator


def execute_rule(
    rule_name: str,
    fields: dict[str, Any],
    ctx: InferenceContext,
) -> InferenceResult | None:
    if rule_name not in _REGISTRY:
        msg = f"rule {rule_name!r} not found in registry"
        raise KeyError(msg)
    return _REGISTRY[rule_name](fields, ctx)


def list_registered_rules() -> list[str]:
    return sorted(_REGISTRY.keys())


# ── Rules ──────────────────────────────────────────────────────────────────────

@_register("infer_company_size_tier")
def infer_company_size_tier(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    employees = fields.get("employee_count")
    revenue = fields.get("annual_revenue_usd")

    if employees is not None:
        e = int(employees)
        if e >= 500:
            return InferenceResult(value="large", confidence=0.85, rule="infer_company_size_tier")
        if e >= 50:
            return InferenceResult(value="mid", confidence=0.80, rule="infer_company_size_tier")
        if e >= 10:
            return InferenceResult(value="small", confidence=0.75, rule="infer_company_size_tier")
        return InferenceResult(value="micro", confidence=0.70, rule="infer_company_size_tier")

    if revenue is not None:
        r = float(revenue)
        if r >= 50_000_000:
            return InferenceResult(value="large", confidence=0.70, rule="infer_company_size_tier")
        if r >= 5_000_000:
            return InferenceResult(value="mid", confidence=0.65, rule="infer_company_size_tier")
        return InferenceResult(value="small", confidence=0.60, rule="infer_company_size_tier")

    return None


@_register("infer_facility_tier_from_capacity")
def infer_facility_tier_from_capacity(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    capacity = fields.get("processing_capacity_tons_per_year")
    if capacity is None:
        return None
    c = float(capacity)
    if c >= 30_000:
        return InferenceResult(value="large", confidence=0.75, rule="infer_facility_tier_from_capacity")
    if c >= 5_000:
        return InferenceResult(value="mid", confidence=0.70, rule="infer_facility_tier_from_capacity")
    if c >= 500:
        return InferenceResult(value="small", confidence=0.65, rule="infer_facility_tier_from_capacity")
    return InferenceResult(value="micro", confidence=0.60, rule="infer_facility_tier_from_capacity")


@_register("infer_material_grade_from_mfi")
def infer_material_grade_from_mfi(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    mfi = fields.get("melt_flow_index")
    material = str(fields.get("material_type", "")).upper()
    if mfi is None or not material:
        return None
    mfi = float(mfi)

    # HDPE grade bands
    if material == "HDPE":
        if mfi < 1.0:
            return InferenceResult(value="HD_pipe", confidence=0.82, rule="infer_material_grade_from_mfi")
        if mfi <= 8.0:
            return InferenceResult(value="HD_injection", confidence=0.82, rule="infer_material_grade_from_mfi")
        return InferenceResult(value="HD_film", confidence=0.78, rule="infer_material_grade_from_mfi")

    # PP grade bands
    if material == "PP":
        if mfi < 5.0:
            return InferenceResult(value="PP_extrusion", confidence=0.80, rule="infer_material_grade_from_mfi")
        if mfi <= 20.0:
            return InferenceResult(value="PP_injection", confidence=0.80, rule="infer_material_grade_from_mfi")
        return InferenceResult(value="PP_fiber", confidence=0.75, rule="infer_material_grade_from_mfi")

    return None


@_register("infer_contamination_tolerance")
def infer_contamination_tolerance(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    tier = str(fields.get("facility_tier", "")).lower()
    grade = str(fields.get("material_grade", "")).lower()

    if not tier:
        return None

    # Micro facilities and pipe-grade materials tolerate higher contamination
    if tier == "micro" or "pipe" in grade:
        return InferenceResult(value="high", confidence=0.72, rule="infer_contamination_tolerance")
    if tier in ("small", "mid"):
        return InferenceResult(value="medium", confidence=0.68, rule="infer_contamination_tolerance")
    if tier == "large":
        return InferenceResult(value="low", confidence=0.74, rule="infer_contamination_tolerance")
    return None


@_register("infer_icp_fit_score")
def infer_icp_fit_score(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    score = 0.0
    factors = 0

    if fields.get("facility_tier") in ("large", "mid"):
        score += 0.3
        factors += 1
    if fields.get("contamination_tolerance") == "low":
        score += 0.25
        factors += 1
    if fields.get("material_grade"):
        score += 0.2
        factors += 1
    if fields.get("certifications"):
        score += 0.15
        factors += 1
    if fields.get("annual_revenue_usd", 0) >= 5_000_000:
        score += 0.1
        factors += 1

    if factors < 2:
        return None  # insufficient signal

    confidence = min(0.50 + factors * 0.07, 0.90)
    return InferenceResult(value=round(score, 3), confidence=confidence, rule="infer_icp_fit_score")


@_register("infer_buyer_persona")
def infer_buyer_persona(
    fields: dict[str, Any], ctx: InferenceContext
) -> InferenceResult | None:
    tier = str(fields.get("facility_tier", "")).lower()
    grade = str(fields.get("material_grade", "")).lower()
    tol = str(fields.get("contamination_tolerance", "")).lower()

    if not tier:
        return None

    if tier == "large" and tol == "low":
        return InferenceResult(value="prime_buyer", confidence=0.78, rule="infer_buyer_persona")
    if tier in ("mid", "large") and "injection" in grade:
        return InferenceResult(value="processor", confidence=0.74, rule="infer_buyer_persona")
    if tol == "high" or tier == "micro":
        return InferenceResult(value="opportunistic_buyer", confidence=0.70, rule="infer_buyer_persona")
    return InferenceResult(value="standard_buyer", confidence=0.62, rule="infer_buyer_persona")
