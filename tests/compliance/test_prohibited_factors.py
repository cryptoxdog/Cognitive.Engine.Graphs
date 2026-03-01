"""
tests/compliance/test_prohibited_factors.py

CRITICAL: Compliance tests for prohibited factors (ECOA, HIPAA, FMCSA, etc.)
Target Coverage: 95%+

These tests verify that the engine correctly blocks prohibited factors at
compile-time, preventing discriminatory matching criteria.
"""

import pytest
from engine.gates.compiler import GateCompiler

from engine.compliance.prohibited_factors import ProhibitedFactorError, ProhibitedFactorValidator

# ============================================================================
# ECOA COMPLIANCE TESTS (Equal Credit Opportunity Act)
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestECOACompliance:
    """Test ECOA prohibited factor enforcement."""

    def test_ecoa_blocks_race_in_gate(self, ecoa_prohibited_fields):
        """ECOA: Race in gate candidateprop should raise error."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "race_gate",
            "type": "threshold",
            "candidateprop": "race",  # PROHIBITED
            "queryparam": "race",
            "operator": "==",
        }

        with pytest.raises(ProhibitedFactorError) as exc_info:
            validator.validate_gate(gate_config)

        assert "race" in str(exc_info.value).lower()
        assert "ECOA" in str(exc_info.value)

    def test_ecoa_blocks_ethnicity_in_gate(self, ecoa_prohibited_fields):
        """ECOA: Ethnicity in gate should raise error."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "ethnicity_gate",
            "type": "enummap",
            "candidateprop": "ethnicity",  # PROHIBITED
            "queryparam": "ethnicity",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_ecoa_blocks_gender_in_query_param(self, ecoa_prohibited_fields):
        """ECOA: Gender in queryparam should raise error."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "gender_gate",
            "type": "boolean",
            "candidateprop": "acceptsmale",
            "queryparam": "gender",  # PROHIBITED
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_ecoa_blocks_age_in_scoring(self, ecoa_prohibited_fields):
        """ECOA: Age in scoring dimension should raise error."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        scoring_config = {
            "name": "age_score",
            "source": "candidateproperty",
            "candidateprop": "age",  # PROHIBITED
            "computation": "candidateproperty",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_scoring_dimension(scoring_config)

    def test_ecoa_blocks_marital_status(self, ecoa_prohibited_fields):
        """ECOA: Marital status should be blocked."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "marital_gate",
            "type": "boolean",
            "candidateprop": "maritalstatus",  # PROHIBITED
            "queryparam": "married",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_ecoa_allows_creditscore(self, ecoa_prohibited_fields):
        """ECOA: Credit score (non-prohibited) should be allowed."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "credit_min",
            "type": "threshold",
            "candidateprop": "mincreditscore",  # ALLOWED
            "queryparam": "creditscore",
            "operator": "<=",
        }

        # Should not raise
        validator.validate_gate(gate_config)

    def test_ecoa_allows_income(self, ecoa_prohibited_fields):
        """ECOA: Income (non-prohibited) should be allowed."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        scoring_config = {
            "name": "income_score",
            "source": "candidateproperty",
            "candidateprop": "annualincome",  # ALLOWED
            "computation": "candidateproperty",
        }

        # Should not raise
        validator.validate_scoring_dimension(scoring_config)

    def test_ecoa_case_insensitive_matching(self, ecoa_prohibited_fields):
        """ECOA: Prohibited field matching should be case-insensitive."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        gate_configs = [
            {"candidateprop": "Race"},  # Capital R
            {"candidateprop": "RACE"},  # All caps
            {"candidateprop": "rAcE"},  # Mixed case
        ]

        for config in gate_configs:
            config["name"] = "test"
            config["type"] = "threshold"
            config["queryparam"] = "value"
            config["operator"] = "=="

            with pytest.raises(ProhibitedFactorError):
                validator.validate_gate(config)

    def test_ecoa_substring_matching(self, ecoa_prohibited_fields):
        """ECOA: Fields containing prohibited substrings should be blocked."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=ecoa_prohibited_fields, enforcement="compiletime"
        )

        # Fields containing "race" substring
        gate_configs = [
            {"candidateprop": "racecode"},
            {"candidateprop": "applicantrace"},
            {"candidateprop": "race_category"},
        ]

        for config in gate_configs:
            config["name"] = "test"
            config["type"] = "threshold"
            config["queryparam"] = "value"
            config["operator"] = "=="

            with pytest.raises(ProhibitedFactorError):
                validator.validate_gate(config)


# ============================================================================
# HIPAA COMPLIANCE TESTS (Health Insurance Portability and Accountability Act)
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestHIPAACompliance:
    """Test HIPAA prohibited factor and PII enforcement."""

    def test_hipaa_blocks_genetic_information(self, hipaa_prohibited_fields):
        """HIPAA: Genetic information in gate should raise error."""
        validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=hipaa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "genetic_gate",
            "type": "boolean",
            "candidateprop": "geneticinformation",  # PROHIBITED
            "queryparam": "hasgenetic",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_hipaa_blocks_disability_in_scoring(self, hipaa_prohibited_fields):
        """HIPAA: Disability in scoring should raise error."""
        validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=hipaa_prohibited_fields, enforcement="compiletime"
        )

        scoring_config = {
            "name": "disability_score",
            "source": "candidateproperty",
            "candidateprop": "disability",  # PROHIBITED
            "computation": "candidateproperty",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_scoring_dimension(scoring_config)

    def test_hipaa_allows_medical_specialty(self, hipaa_prohibited_fields):
        """HIPAA: Medical specialty (non-prohibited) should be allowed."""
        validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=hipaa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "specialty_gate",
            "type": "enummap",
            "candidateprop": "specialty",  # ALLOWED
            "queryparam": "specialty",
        }

        # Should not raise
        validator.validate_gate(gate_config)

    def test_hipaa_allows_condition_matching(self, hipaa_prohibited_fields):
        """HIPAA: Primary condition matching should be allowed."""
        validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=hipaa_prohibited_fields, enforcement="compiletime"
        )

        gate_config = {
            "name": "condition_gate",
            "type": "enummap",
            "candidateprop": "treatedconditions",  # ALLOWED
            "queryparam": "primarycondition",
        }

        # Should not raise
        validator.validate_gate(gate_config)


# ============================================================================
# MULTI-REGIME COMPLIANCE TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestMultiRegimeCompliance:
    """Test multiple compliance regimes simultaneously."""

    def test_multiple_regimes_block_overlapping_fields(self):
        """Multiple regimes should block all their prohibited fields."""
        ecoa_validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=["race", "ethnicity", "gender"], enforcement="compiletime"
        )

        hipaa_validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=["race", "ethnicity", "geneticinformation"], enforcement="compiletime"
        )

        # Race blocked by both
        gate_config = {
            "name": "race_gate",
            "type": "threshold",
            "candidateprop": "race",
            "queryparam": "race",
            "operator": "==",
        }

        with pytest.raises(ProhibitedFactorError):
            ecoa_validator.validate_gate(gate_config)

        with pytest.raises(ProhibitedFactorError):
            hipaa_validator.validate_gate(gate_config)

    def test_multiple_regimes_unique_fields(self):
        """Each regime should block its unique prohibited fields."""
        ecoa_validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=["maritalstatus"], enforcement="compiletime"
        )

        hipaa_validator = ProhibitedFactorValidator(
            regime="HIPAA", blocked_fields=["geneticinformation"], enforcement="compiletime"
        )

        # Marital status blocked by ECOA only
        marital_config = {
            "name": "marital_gate",
            "type": "boolean",
            "candidateprop": "maritalstatus",
            "queryparam": "married",
        }

        with pytest.raises(ProhibitedFactorError):
            ecoa_validator.validate_gate(marital_config)

        # Should not raise for HIPAA
        hipaa_validator.validate_gate(marital_config)

        # Genetic info blocked by HIPAA only
        genetic_config = {
            "name": "genetic_gate",
            "type": "boolean",
            "candidateprop": "geneticinformation",
            "queryparam": "hasgenetic",
        }

        with pytest.raises(ProhibitedFactorError):
            hipaa_validator.validate_gate(genetic_config)

        # Should not raise for ECOA
        ecoa_validator.validate_gate(genetic_config)


# ============================================================================
# GATE COMPILER INTEGRATION TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.integration
class TestProhibitedFactorsInCompilation:
    """Test prohibited factor enforcement during gate compilation."""

    def test_compiler_blocks_prohibited_gate(self, mortgage_domain_spec):
        """Gate compiler should block gates with prohibited factors."""
        # Inject prohibited field into gate
        prohibited_gate = {
            "name": "race_gate",
            "type": "threshold",
            "candidateprop": "race",  # PROHIBITED by ECOA
            "queryparam": "race",
            "operator": "==",
        }

        mortgage_domain_spec["gates"].append(prohibited_gate)

        compiler = GateCompiler(domain_spec=mortgage_domain_spec)

        with pytest.raises(ProhibitedFactorError):
            compiler.compile_all_gates(match_direction="borrowertoproduct")

    def test_compiler_allows_compliant_gates(self, mortgage_domain_spec):
        """Gate compiler should allow gates without prohibited factors."""
        compiler = GateCompiler(domain_spec=mortgage_domain_spec)

        # Should not raise (all gates in spec are compliant)
        cypher = compiler.compile_all_gates(match_direction="borrowertoproduct")

        assert cypher is not None
        assert "race" not in cypher.lower()
        assert "ethnicity" not in cypher.lower()
        assert "gender" not in cypher.lower()


# ============================================================================
# ENFORCEMENT MODE TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestEnforcementModes:
    """Test different enforcement modes for prohibited factors."""

    def test_compiletime_enforcement_blocks_immediately(self):
        """Compile-time enforcement should block at gate definition."""
        validator = ProhibitedFactorValidator(
            regime="ECOA",
            blocked_fields=["race"],
            enforcement="compiletime",  # Block at compile time
        )

        gate_config = {"name": "race_gate", "candidateprop": "race", "queryparam": "race"}

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_runtime_enforcement_allows_definition(self):
        """Runtime enforcement should allow definition, block at execution."""
        validator = ProhibitedFactorValidator(
            regime="ECOA",
            blocked_fields=["race"],
            enforcement="runtime",  # Allow definition, block at runtime
        )

        gate_config = {"name": "race_gate", "candidateprop": "race", "queryparam": "race"}

        # Should not raise at definition time
        validator.validate_gate(gate_config)

        # NOTE: Runtime blocking would happen during query execution
        # (tested in integration tests)

    def test_disabled_enforcement_allows_all(self):
        """Disabled enforcement should allow prohibited fields."""
        validator = ProhibitedFactorValidator(
            regime="ECOA",
            blocked_fields=["race"],
            enforcement="disabled",  # No enforcement
        )

        gate_config = {"name": "race_gate", "candidateprop": "race", "queryparam": "race"}

        # Should not raise
        validator.validate_gate(gate_config)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestProhibitedFactorEdgeCases:
    """Test edge cases for prohibited factor validation."""

    def test_empty_blocked_fields_allows_all(self):
        """Empty blocked fields list should allow all fields."""
        validator = ProhibitedFactorValidator(
            regime="TEST",
            blocked_fields=[],  # Empty list
            enforcement="compiletime",
        )

        gate_config = {"name": "any_gate", "candidateprop": "race", "queryparam": "race"}

        # Should not raise
        validator.validate_gate(gate_config)

    def test_none_blocked_fields_allows_all(self):
        """None blocked fields should allow all fields."""
        validator = ProhibitedFactorValidator(
            regime="TEST",
            blocked_fields=None,  # None
            enforcement="compiletime",
        )

        gate_config = {"name": "any_gate", "candidateprop": "race", "queryparam": "race"}

        # Should not raise
        validator.validate_gate(gate_config)

    def test_whitespace_in_field_names(self):
        """Fields with whitespace should be handled correctly."""
        validator = ProhibitedFactorValidator(regime="TEST", blocked_fields=["race"], enforcement="compiletime")

        gate_config = {
            "name": "test",
            "candidateprop": " race ",  # Whitespace
            "queryparam": "value",
        }

        # Should block after trimming
        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)

    def test_special_characters_in_field_names(self):
        """Fields with special characters should be handled."""
        validator = ProhibitedFactorValidator(regime="TEST", blocked_fields=["race"], enforcement="compiletime")

        # Underscores, hyphens common in field names
        gate_configs = [
            {"candidateprop": "race_code"},
            {"candidateprop": "race-code"},
            {"candidateprop": "applicant_race"},
        ]

        for config in gate_configs:
            config["name"] = "test"
            config["queryparam"] = "value"

            with pytest.raises(ProhibitedFactorError):
                validator.validate_gate(config)

    def test_numeric_field_names(self):
        """Numeric field names should be handled."""
        validator = ProhibitedFactorValidator(regime="TEST", blocked_fields=["field123"], enforcement="compiletime")

        gate_config = {"name": "test", "candidateprop": "field123", "queryparam": "value"}

        with pytest.raises(ProhibitedFactorError):
            validator.validate_gate(gate_config)


# ============================================================================
# VALIDATION SCOPE TESTS
# ============================================================================


@pytest.mark.compliance
@pytest.mark.unit
class TestValidationScope:
    """Test validation across different configuration scopes."""

    def test_validate_entire_domain_spec(self, mortgage_domain_spec):
        """Validator should check entire domain specification."""
        validator = ProhibitedFactorValidator(
            regime="ECOA", blocked_fields=["race", "ethnicity", "gender"], enforcement="compiletime"
        )

        # Inject prohibited field in scoring
        mortgage_domain_spec["scoring"]["dimensions"].append(
            {
                "name": "race_score",
                "source": "candidateproperty",
                "candidateprop": "race",  # PROHIBITED
                "computation": "candidateproperty",
            }
        )

        with pytest.raises(ProhibitedFactorError):
            validator.validate_domain_spec(mortgage_domain_spec)

    def test_validate_query_schema(self):
        """Validator should check query schema fields."""
        validator = ProhibitedFactorValidator(regime="ECOA", blocked_fields=["race"], enforcement="compiletime")

        query_schema = {
            "fields": [
                {"name": "borrowerid", "type": "string"},
                {"name": "race", "type": "string"},  # PROHIBITED
            ]
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_query_schema(query_schema)

    def test_validate_derived_parameters(self):
        """Validator should check derived parameter expressions."""
        validator = ProhibitedFactorValidator(regime="ECOA", blocked_fields=["age"], enforcement="compiletime")

        derived_param = {
            "name": "age_adjusted_income",
            "expression": "annualincome / age",  # Uses prohibited 'age'
            "type": "float",
        }

        with pytest.raises(ProhibitedFactorError):
            validator.validate_derived_parameter(derived_param)
