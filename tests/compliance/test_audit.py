# ============================================================================
# tests/compliance/test_audit.py
# ============================================================================

"""
Audit logging compliance tests.
Target Coverage: 90%+
"""

import pytest

from engine.compliance.audit import DEFAULT_RETENTION, AuditAction, AuditLogger, AuditSeverity


@pytest.mark.compliance
@pytest.mark.unit
class TestAuditLogging:
    """Test audit log generation."""

    def test_log_access(self) -> None:
        """Access events are logged with correct structure."""
        logger = AuditLogger()

        entry = logger.log_access(
            actor="test_user",
            tenant="plasticos",
            resource="Facility:42",
            resource_type="Facility",
            trace_id="trace-123",
        )

        assert entry.action == AuditAction.ACCESS
        assert entry.actor == "test_user"
        assert entry.tenant == "plasticos"
        assert entry.resource == "Facility:42"
        assert entry.outcome == "success"

    def test_log_mutation(self) -> None:
        """Mutation events are logged with payload hash."""
        logger = AuditLogger()

        entry = logger.log_mutation(
            actor="sync_service",
            tenant="plasticos",
            resource="MaterialProfile:7",
            detail="Batch sync 150 entities",
            payload_hash="abc123hash",
            compliance_tags=["GDPR", "SOC2"],
        )

        assert entry.action == AuditAction.MUTATION
        assert entry.detail == "Batch sync 150 entities"
        assert entry.payload_hash == "abc123hash"
        assert "GDPR" in entry.compliance_tags

    def test_log_query(self) -> None:
        """Query events are logged."""
        logger = AuditLogger()

        entry = logger.log_query(
            actor="api",
            tenant="mortgage",
            detail="match_strict 14 gates",
            trace_id="trace-456",
        )

        assert entry.action == AuditAction.QUERY
        assert entry.severity == AuditSeverity.INFO

    def test_log_pii_erasure(self) -> None:
        """PII erasure events are logged with CRITICAL severity."""
        logger = AuditLogger()

        entry = logger.log_pii_erasure(
            actor="gdpr_service",
            tenant="healthcare",
            data_subject_id="user-123",
            detail="Right-to-erasure request processed",
        )

        assert entry.action == AuditAction.PII_ERASURE
        assert entry.severity == AuditSeverity.CRITICAL
        assert entry.data_subject_id == "user-123"
        assert "GDPR" in entry.compliance_tags

    def test_pii_access_warning_severity(self) -> None:
        """Access with PII fields triggers WARNING severity."""
        logger = AuditLogger()

        entry = logger.log_access(
            actor="analyst",
            tenant="healthcare",
            resource="Patient:99",
            pii_fields_accessed=["ssn", "dob"],
        )

        assert entry.severity == AuditSeverity.WARNING
        assert "ssn" in entry.pii_fields_accessed

    def test_retention_policy_lookup(self) -> None:
        """Retention policies return correct days."""
        logger = AuditLogger(retention_policies=DEFAULT_RETENTION)

        # SOC2 = 2555 days (7 years)
        assert logger.get_retention_days(["SOC2"]) == 2555

        # HIPAA = 2190 days (6 years)
        assert logger.get_retention_days(["HIPAA"]) == 2190

        # Multiple tags = longest retention wins
        assert logger.get_retention_days(["GDPR", "SOC2"]) == 2555

        # No tags = default 365
        assert logger.get_retention_days([]) == 365

    @pytest.mark.asyncio
    async def test_buffer_and_flush(self) -> None:
        """Audit entries buffer and flush correctly."""
        logger = AuditLogger(buffer_size=3)

        logger.log_access(actor="u1", tenant="t1", resource="r1")
        logger.log_access(actor="u2", tenant="t1", resource="r2")

        assert logger.buffer_count == 2

        entries = await logger.flush()
        assert len(entries) == 2
        assert logger.buffer_count == 0
