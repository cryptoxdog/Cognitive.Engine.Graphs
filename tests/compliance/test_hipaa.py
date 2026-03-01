# ============================================================================
# tests/compliance/test_hipaa.py
# ============================================================================

"""
HIPAA compliance tests (PII handling, prohibited factors).
Target Coverage: 95%+
"""

import pytest
from engine.compliance.pii import PIIHandler


@pytest.mark.compliance
@pytest.mark.unit
class TestHIPAAPII:
    """Test HIPAA PII handling."""

    def test_pii_hashing(self, hipaa_pii_fields):
        """PII fields are hashed when handling=hash."""
        handler = PIIHandler(pii_fields=hipaa_pii_fields, handling="hash")

        data = {"patientid": "PAT_12345", "name": "John Doe", "ssn": "123-45-6789"}

        processed = handler.process(data)

        assert processed["patientid"] != "PAT_12345"  # Hashed
        assert processed["ssn"] != "123-45-6789"  # Hashed
        assert len(processed["patientid"]) == 64  # SHA256 hash length

    def test_pii_redaction(self, hipaa_pii_fields):
        """PII fields are redacted when handling=redact."""
        handler = PIIHandler(pii_fields=hipaa_pii_fields, handling="redact")

        data = {"patientid": "PAT_12345", "age": 45, "ssn": "123-45-6789"}

        processed = handler.process(data)

        assert processed["patientid"] == "[REDACTED]"
        assert processed["ssn"] == "[REDACTED]"
        assert processed["age"] == 45  # Non-PII preserved

    def test_pii_encryption(self, hipaa_pii_fields):
        """PII fields are encrypted when handling=encrypt."""
        handler = PIIHandler(
            pii_fields=hipaa_pii_fields, handling="encrypt", encryption_key="test_key_32_characters_long123"
        )

        data = {"patientid": "PAT_12345"}

        processed = handler.process(data)
        decrypted = handler.decrypt(processed)

        assert processed["patientid"] != "PAT_12345"  # Encrypted
        assert decrypted["patientid"] == "PAT_12345"  # Decrypts correctly
