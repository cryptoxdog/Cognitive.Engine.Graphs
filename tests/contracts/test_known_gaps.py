"""
Known gap tracker — tests that are expected to fail until the gap is filled.

Each test corresponds to a known architectural gap identified in the
CEG_Gap_Analysis_Frontier_Labs.md or the contract extraction process.
These tests use xfail to document what's missing without breaking CI.
"""

import pytest

from tests.contracts._constants import CONTRACTS_ROOT

# ── Evaluation infrastructure ────────────────────────────────────────────────


@pytest.mark.xfail(reason="GAP: No eval infra yet — no benchmark runner or metrics pipeline")
def test_eval_infra_contract_exists():
    path = CONTRACTS_ROOT / "eval" / "eval-pipeline.yaml"
    assert path.exists()


@pytest.mark.xfail(reason="GAP: No automated benchmarking contracts")
def test_benchmark_contract_exists():
    path = CONTRACTS_ROOT / "eval" / "benchmarks.yaml"
    assert path.exists()


# ── Self-improvement / feedback loops ────────────────────────────────────────


@pytest.mark.xfail(reason="GAP: Feedback convergence loop not yet contracted")
def test_feedback_convergence_contract_exists():
    path = CONTRACTS_ROOT / "feedback" / "convergence-loop.yaml"
    assert path.exists()


# ── Observability depth ──────────────────────────────────────────────────────


@pytest.mark.xfail(reason="GAP: No OpenTelemetry trace contract")
def test_otel_trace_contract_exists():
    path = CONTRACTS_ROOT / "observability" / "otel-traces.yaml"
    assert path.exists()


@pytest.mark.xfail(reason="GAP: No SLO contract defined")
def test_slo_contract_exists():
    path = CONTRACTS_ROOT / "observability" / "slo-definitions.yaml"
    assert path.exists()


# ── Access control ───────────────────────────────────────────────────────────


@pytest.mark.xfail(reason="GAP: RBAC model not yet contracted — JWT_SECRET flag exists but no policy")
def test_rbac_policy_contract_exists():
    path = CONTRACTS_ROOT / "auth" / "rbac-policy.yaml"
    assert path.exists()


# ── Tool schema completeness ────────────────────────────────────────────────

TOOL_SCHEMAS_EXPECTED = {"match", "sync", "admin", "outcomes", "resolve", "enrich"}


@pytest.mark.parametrize("name", sorted(TOOL_SCHEMAS_EXPECTED))
@pytest.mark.xfail(reason="GAP: Individual tool schemas not yet generated")
def test_individual_tool_schema_exists(name):
    path = CONTRACTS_ROOT / "agents" / "tool-schemas" / f"{name}.schema.json"
    assert path.exists()
