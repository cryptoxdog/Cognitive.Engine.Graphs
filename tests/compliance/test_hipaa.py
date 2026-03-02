# ============================================================================
# tests/compliance/test_hipaa.py
# ============================================================================

"""
HIPAA compliance tests (PII handling, prohibited factors).
Target Coverage: 95%+
"""

import pytest

from engine.compliance.pii import PIICategory, PIIHandler, PIISensitivity


@pytest.mark.compliance
@pytest.mark.unit
class TestPIIDetection:
    """Test PII detection capabilities."""

    def test_detect_email_by_field_name(self) -> None:
        """Email fields detected by field name hint."""
        handler = PIIHandler()
        payload = {"contact_email": "test@example.com", "facility_id": 42}

        detections = handler.detect_pii(payload)

        assert len(detections) == 1
        assert detections[0].field_path == "contact_email"
        assert detections[0].category == PIICategory.EMAIL
        assert detections[0].detected_by == "field_name"

    def test_detect_ssn_by_pattern(self) -> None:
        """SSN detected by regex pattern in value."""
        handler = PIIHandler()
        payload = {"notes": "SSN is 123-45-6789", "id": 1}

        detections = handler.detect_pii(payload)

        assert len(detections) == 1
        assert detections[0].category == PIICategory.SSN
        assert detections[0].detected_by == "pattern_match"

    def test_detect_nested_pii(self) -> None:
        """PII detected in nested dicts."""
        handler = PIIHandler()
        payload = {
            "patient": {
                "first_name": "John",
                "contact": {"phone": "555-123-4567"},
            }
        }

        detections = handler.detect_pii(payload)
        paths = [d.field_path for d in detections]

        assert "patient.first_name" in paths
        assert "patient.contact.phone" in paths

    def test_get_pii_field_paths(self) -> None:
        """get_pii_field_paths returns tuple for PacketEnvelope."""
        handler = PIIHandler()
        payload = {"email": "a@b.com", "ssn": "111-22-3333", "id": 1}

        pii_fields = handler.get_pii_field_paths(payload)

        assert isinstance(pii_fields, tuple)
        assert "email" in pii_fields
        assert "ssn" in pii_fields


@pytest.mark.compliance
@pytest.mark.unit
class TestPIIMasking:
    """Test PII masking capabilities."""

    def test_mask_email(self) -> None:
        """Email masked with domain hint preserved."""
        handler = PIIHandler()
        payload = {"email": "john.doe@example.com"}

        masked = handler.mask_fields(payload, fields=["email"])

        assert masked["email"] != "john.doe@example.com"
        assert "@" in masked["email"]
        assert "com" in masked["email"]

    def test_mask_ssn(self) -> None:
        """SSN masked with last 4 visible."""
        handler = PIIHandler()
        payload = {"ssn": "123-45-6789"}

        masked = handler.mask_fields(payload, fields=["ssn"])

        assert masked["ssn"].endswith("6789")
        assert "*" in masked["ssn"]

    def test_mask_all_detected(self) -> None:
        """mask_all_detected auto-detects and masks PII."""
        handler = PIIHandler()
        payload = {"email": "test@test.com", "phone": "555-1234", "id": 42}

        masked = handler.mask_fields(payload, mask_all_detected=True)

        assert masked["email"] != "test@test.com"
        assert masked["id"] == 42  # Non-PII unchanged


@pytest.mark.compliance
@pytest.mark.unit
class TestPIIRedaction:
    """Test PII redaction (removal)."""

    def test_redact_fields(self) -> None:
        """Redact removes specified fields entirely."""
        handler = PIIHandler()
        payload = {"ssn": "123-45-6789", "name": "John", "age": 30}

        redacted = handler.redact(payload, fields=["ssn"])

        assert "ssn" not in redacted
        assert redacted["name"] == "John"
        assert redacted["age"] == 30

    def test_redact_all_detected(self) -> None:
        """redact_all_detected removes all PII fields."""
        handler = PIIHandler()
        payload = {"email": "a@b.com", "phone": "555-1234", "facility_id": 42}

        redacted = handler.redact(payload, redact_all_detected=True)

        assert "email" not in redacted
        assert "phone" not in redacted
        assert redacted["facility_id"] == 42


@pytest.mark.compliance
@pytest.mark.unit
class TestPIIHashing:
    """Test PII hashing for pseudonymization."""

    def test_hash_deterministic(self) -> None:
        """Same input produces same hash."""
        h1 = PIIHandler.hash_value("test@example.com")
        h2 = PIIHandler.hash_value("test@example.com")

        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_hash_with_salt(self) -> None:
        """Salt changes hash output."""
        h1 = PIIHandler.hash_value("test@example.com", salt="")
        h2 = PIIHandler.hash_value("test@example.com", salt="secret")

        assert h1 != h2


@pytest.mark.compliance
@pytest.mark.unit
class TestCustomPIIFields:
    """Test custom PII field registration."""

    def test_additional_pii_fields(self) -> None:
        """Custom PII fields are detected."""
        handler = PIIHandler(
            additional_pii_fields={
                "mrn": (PIICategory.CUSTOM, PIISensitivity.HIGH),
                "patient_id": (PIICategory.CUSTOM, PIISensitivity.HIGH),
            }
        )

        payload = {"mrn": "MRN12345", "facility": "Hospital A"}
        detections = handler.detect_pii(payload)

        assert len(detections) == 1
        assert detections[0].field_path == "mrn"
        assert detections[0].sensitivity == PIISensitivity.HIGH
