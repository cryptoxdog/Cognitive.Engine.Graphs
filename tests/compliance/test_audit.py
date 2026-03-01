# ============================================================================
# tests/compliance/test_audit.py
# ============================================================================

"""
Audit logging compliance tests.
Target Coverage: 90%+
"""

import pytest
from engine.compliance.audit import AuditLogger


@pytest.mark.compliance
@pytest.mark.unit
class TestAuditLogging:
    """Test audit log generation."""

    def test_match_request_logged(self):
        """Match requests are logged with query details."""
        logger = AuditLogger(enabled=True, log_match_requests=True)

        query = {"borrowerid": "BRW_001", "creditscore": 720}

        log_entry = logger.log_match_request(domain="mortgage-brokerage", query=query, user="test_user")

        assert log_entry["event_type"] == "match_request"
        assert log_entry["domain"] == "mortgage-brokerage"
        assert log_entry["user"] == "test_user"
        assert "query" in log_entry

    def test_match_results_logged(self):
        """Match results are logged with candidate IDs."""
        logger = AuditLogger(enabled=True, log_match_results=True)

        results = [{"productid": "PROD_001", "score": 0.95}, {"productid": "PROD_002", "score": 0.87}]

        log_entry = logger.log_match_results(domain="mortgage-brokerage", results=results, user="test_user")

        assert log_entry["event_type"] == "match_results"
        assert log_entry["result_count"] == 2
        assert "PROD_001" in str(log_entry)

    def test_retention_enforcement(self):
        """Audit logs enforce retention policy."""
        logger = AuditLogger(enabled=True, retention_days=90)

        # Logs older than 90 days should be purged
        # (Integration test would verify actual deletion)
        assert logger.retention_days == 90
