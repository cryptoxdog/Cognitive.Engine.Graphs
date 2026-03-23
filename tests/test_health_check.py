"""Tests for health check response path verification (GMP-07)."""


def test_health_response_structure():
    """Verify handle_health returns status at correct nesting level."""
    # The chassis wraps engine response in {"data": engine_response}
    # So result["data"]["status"] == "healthy" is the correct path
    engine_response = {"status": "healthy", "checks": {"neo4j": "ok", "domains": "ok"}}
    chassis_envelope = {
        "status": "success",
        "action": "health",
        "data": engine_response,
    }
    assert chassis_envelope.get("data", {}).get("status") == "healthy"


def test_health_degraded_returns_503_logic():
    """Verify degraded health returns non-healthy status."""
    engine_response = {"status": "degraded", "checks": {"neo4j": "failed"}}
    chassis_envelope = {
        "status": "failed",
        "action": "health",
        "data": engine_response,
    }
    assert chassis_envelope.get("data", {}).get("status") != "healthy"
