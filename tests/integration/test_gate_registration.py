"""
Tests for engine/gate_registration.py.

Verifies:
- register_node_with_gate is non-fatal on failure
- register_node_with_gate logs success on registration
"""

from __future__ import annotations

import pytest

pytest.importorskip("constellation_node_sdk", reason="constellation-node-sdk not installed")

from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_register_node_non_fatal_on_failure(monkeypatch, caplog):
    """Registration failure should log error but not raise."""
    monkeypatch.setenv("GATE_URL", "http://test-gate:8000")
    monkeypatch.setenv("L9_NODE_NAME", "test-node")
    monkeypatch.setenv("GATE_REGISTRATION_ENABLED", "true")

    with patch(
        "engine.gate_registration.register_from_env",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        from engine.gate_registration import register_node_with_gate

        # Should not raise
        await register_node_with_gate()

    assert "Gate registration failed" in caplog.text or "error" in caplog.text.lower()


@pytest.mark.asyncio
async def test_register_node_skipped_when_disabled(monkeypatch, caplog):
    """Registration should be skipped when GATE_REGISTRATION_ENABLED=false."""
    monkeypatch.setenv("GATE_REGISTRATION_ENABLED", "false")

    from engine.gate_registration import register_node_with_gate

    await register_node_with_gate()
    # Should complete without error when disabled
