# ============================================================================
# tests/unit/test_config.py
# ============================================================================

"""
Configuration schema validation tests.
Target Coverage: 70%+
"""

import pytest
from pydantic import ValidationError

from engine.config.schema import DomainSpec


@pytest.mark.unit
class TestConfigValidation:
    """Test Pydantic schema validation."""

    def test_minimal_spec_validates(self, minimal_domain_spec):
        """Minimal valid spec passes validation."""
        spec = DomainSpec(**minimal_domain_spec)
        assert spec.domain.id == "test-domain"

    def test_missing_required_field_fails(self):
        """Missing required field raises ValidationError."""
        invalid_spec = {
            "domain": {"id": "test"},
            # Missing ontology, matchentities, etc.
        }

        with pytest.raises(ValidationError):
            DomainSpec(**invalid_spec)

    def test_invalid_gate_type_fails(self):
        """Invalid gate type raises ValidationError."""
        spec = {
            "domain": {"id": "test", "name": "Test", "version": "1.0.0"},
            "gates": [{"name": "invalid", "type": "INVALID_TYPE"}],
        }

        with pytest.raises(ValidationError):
            DomainSpec(**spec)
