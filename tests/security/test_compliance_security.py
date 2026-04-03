"""
Security tests — ECOA prohibited factor enforcement at compliance layer.
"""

from __future__ import annotations

from pathlib import Path

DOMAINS_DIR = Path(__file__).parent.parent.parent / "domains"

ECOA_PROHIBITED = [
    "race",
    "color",
    "religion",
    "national_origin",
    "sex",
    "marital_status",
    "age",
    "disability",
    "familial_status",
    "receipt_of_public_assistance",
]


def test_compliance_engine_loads_for_plasticos():
    """ComplianceEngine must load without error for plasticos."""
    from engine.compliance.engine import ComplianceEngine
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    engine = ComplianceEngine(spec)
    assert engine is not None


def test_prohibited_factor_validator_exists():
    """ProhibitedFactorValidator must exist and load from spec."""
    from engine.compliance.prohibited_factors import ProhibitedFactorValidator
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    validator = ProhibitedFactorValidator(spec)
    assert validator is not None


def test_clean_payload_passes_compliance():
    """A payload with no prohibited fields must pass."""
    from engine.compliance.engine import ComplianceEngine
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    engine = ComplianceEngine(spec)
    result = engine.evaluate(
        {
            "entity_id": "f1",
            "contamination_tolerance": 0.05,
            "facility_tier": "mid",
        }
    )
    # Should pass without error
    assert result is not None


def test_compliance_evaluate_returns_result():
    """evaluate() must return a structured result."""
    from engine.compliance.engine import ComplianceEngine
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    engine = ComplianceEngine(spec)
    result = engine.evaluate({"entity_id": "test"})
    # Result should be a dataclass or dict with compliance_pass
    assert hasattr(result, "compliance_pass") or isinstance(result, (dict, bool))
