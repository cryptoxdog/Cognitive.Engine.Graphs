"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, compliance, prohibited-factors]
owner: engine-team
status: active
--- /L9_META ---

CRITICAL: Compliance tests for prohibited factors (ECOA, HIPAA, FMCSA, etc.)
Target Coverage: 95%+

These tests verify that the engine correctly blocks prohibited factors at
compile-time, preventing discriminatory matching criteria.
"""

from unittest.mock import MagicMock

import pytest

from engine.compliance.prohibited_factors import ProhibitedFactorValidator
from engine.config.schema import DomainSpec, GateSpec


def make_mock_domain_spec(blocked_fields: list[str] | None = None, enabled: bool = True) -> MagicMock:
    """Create a mock DomainSpec with prohibited factors config."""
    spec = MagicMock(spec=DomainSpec)
    spec.compliance = MagicMock()
    spec.compliance.prohibitedfactors = MagicMock()
    spec.compliance.prohibitedfactors.enabled = enabled
    spec.compliance.prohibitedfactors.blockedfields = blocked_fields or []
    return spec


def make_gate_spec(name: str, candidate_prop: str, query_param: str = "value") -> MagicMock:
    """Create a mock GateSpec."""
    gate = MagicMock(spec=GateSpec)
    gate.name = name
    gate.candidateprop = candidate_prop
    gate.queryparam = query_param
    return gate


# ============================================================================
# ECOA COMPLIANCE TESTS (Equal Credit Opportunity Act)
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestECOACompliance:
    """Test ECOA prohibited factor enforcement."""

    def test_ecoa_blocks_race_in_gate(self) -> None:
        """ECOA: Race in gate candidateprop should raise error."""
        spec = make_mock_domain_spec(blocked_fields=["race", "ethnicity", "gender"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("race_gate", candidate_prop="race")

        with pytest.raises(ValueError) as exc_info:
            validator.validate_gate(gate)

        assert "race" in str(exc_info.value).lower()

    def test_ecoa_blocks_ethnicity_in_gate(self) -> None:
        """ECOA: Ethnicity in gate should raise error."""
        spec = make_mock_domain_spec(blocked_fields=["race", "ethnicity", "gender"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("ethnicity_gate", candidate_prop="ethnicity")

        with pytest.raises(ValueError):
            validator.validate_gate(gate)

    def test_ecoa_blocks_gender_in_query_param(self) -> None:
        """ECOA: Gender in queryparam should raise error."""
        spec = make_mock_domain_spec(blocked_fields=["race", "ethnicity", "gender"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("gender_gate", candidate_prop="acceptsmale", query_param="gender")

        with pytest.raises(ValueError):
            validator.validate_gate(gate)

    def test_ecoa_allows_creditscore(self) -> None:
        """ECOA: Credit score (non-prohibited) should be allowed."""
        spec = make_mock_domain_spec(blocked_fields=["race", "ethnicity", "gender"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("credit_min", candidate_prop="mincreditscore", query_param="creditscore")

        # Should not raise
        validator.validate_gate(gate)

    def test_ecoa_allows_income(self) -> None:
        """ECOA: Income (non-prohibited) should be allowed."""
        spec = make_mock_domain_spec(blocked_fields=["race", "ethnicity", "gender"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("income_gate", candidate_prop="annualincome")

        # Should not raise
        validator.validate_gate(gate)


# ============================================================================
# HIPAA COMPLIANCE TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestHIPAACompliance:
    """Test HIPAA prohibited factor enforcement."""

    def test_hipaa_blocks_genetic_information(self) -> None:
        """HIPAA: Genetic information in gate should raise error."""
        spec = make_mock_domain_spec(blocked_fields=["geneticinformation", "disability"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("genetic_gate", candidate_prop="geneticinformation")

        with pytest.raises(ValueError):
            validator.validate_gate(gate)

    def test_hipaa_allows_medical_specialty(self) -> None:
        """HIPAA: Medical specialty (non-prohibited) should be allowed."""
        spec = make_mock_domain_spec(blocked_fields=["geneticinformation", "disability"])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("specialty_gate", candidate_prop="specialty")

        # Should not raise
        validator.validate_gate(gate)


# ============================================================================
# DISABLED / EMPTY ENFORCEMENT TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestEnforcementModes:
    """Test different enforcement configurations."""

    def test_disabled_enforcement_allows_all(self) -> None:
        """Disabled enforcement should allow all fields."""
        spec = make_mock_domain_spec(blocked_fields=["race"], enabled=False)
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("race_gate", candidate_prop="race")

        # Should not raise when disabled
        validator.validate_gate(gate)

    def test_empty_blocked_fields_allows_all(self) -> None:
        """Empty blocked fields list should allow all fields."""
        spec = make_mock_domain_spec(blocked_fields=[])
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("any_gate", candidate_prop="race")

        # Should not raise
        validator.validate_gate(gate)

    def test_none_compliance_config_allows_all(self) -> None:
        """None compliance config should allow all fields."""
        spec = MagicMock(spec=DomainSpec)
        spec.compliance = None
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("any_gate", candidate_prop="race")

        # Should not raise
        validator.validate_gate(gate)

    def test_none_prohibited_factors_allows_all(self) -> None:
        """None prohibitedfactors config should allow all fields."""
        spec = MagicMock(spec=DomainSpec)
        spec.compliance = MagicMock()
        spec.compliance.prohibitedfactors = None
        validator = ProhibitedFactorValidator(spec)

        gate = make_gate_spec("any_gate", candidate_prop="race")

        # Should not raise
        validator.validate_gate(gate)
