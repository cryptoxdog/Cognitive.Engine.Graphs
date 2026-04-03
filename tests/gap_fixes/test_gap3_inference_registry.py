"""
Tests for GAP-3: inference_rule_registry.py
"""

from __future__ import annotations

import pytest

from engine.inference_rule_registry import (
    InferenceContext,
    execute_rule,
    list_registered_rules,
)

CTX = InferenceContext(tenant_id="t1", domain_id="plastics", pass_number=1)


def test_all_core_rules_registered() -> None:
    rules = list_registered_rules()
    assert "infer_company_size_tier" in rules
    assert "infer_facility_tier_from_capacity" in rules
    assert "infer_material_grade_from_mfi" in rules
    assert "infer_contamination_tolerance" in rules
    assert "infer_icp_fit_score" in rules
    assert "infer_buyer_persona" in rules


def test_facility_tier_large() -> None:
    result = execute_rule(
        "infer_facility_tier_from_capacity",
        {"processing_capacity_tons_per_year": 50000},
        CTX,
    )
    assert result is not None
    assert result.value == "large"
    assert result.confidence >= 0.55


def test_mfi_hdpe_injection() -> None:
    result = execute_rule(
        "infer_material_grade_from_mfi",
        {"melt_flow_index": 5.0, "material_type": "HDPE"},
        CTX,
    )
    assert result is not None
    assert result.value == "HD_injection"


def test_contamination_tolerance_from_tier() -> None:
    result = execute_rule(
        "infer_contamination_tolerance",
        {"facility_tier": "micro", "material_grade": "HD_pipe"},
        CTX,
    )
    assert result is not None
    assert result.value == "high"


def test_unknown_rule_raises() -> None:
    with pytest.raises(KeyError, match="not found in registry"):
        execute_rule("nonexistent_rule", {}, CTX)


def test_low_confidence_suppressed() -> None:
    # icp_fit_score with no contributing factors returns None
    result = execute_rule("infer_icp_fit_score", {}, CTX)
    assert result is None
