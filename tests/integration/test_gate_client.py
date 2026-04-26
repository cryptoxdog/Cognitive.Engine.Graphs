"""
Tests for engine/gate_client.py.

Verifies:
- get_gate_client returns a GateClient instance
- get_gate_client returns the same singleton on repeated calls
- reset_gate_client clears the singleton
"""

from __future__ import annotations

import pytest

pytest.importorskip("constellation_node_sdk", reason="constellation-node-sdk not installed")

from engine.gate_client import get_gate_client, reset_gate_client


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset the singleton before and after each test."""
    reset_gate_client()
    yield
    reset_gate_client()


def test_get_gate_client_returns_client(monkeypatch):
    """get_gate_client returns a GateClient when GATE_URL is set."""
    monkeypatch.setenv("GATE_URL", "http://test-gate:8000")
    monkeypatch.setenv("L9_NODE_NAME", "test-node")
    client = get_gate_client()
    assert client is not None


def test_get_gate_client_singleton(monkeypatch):
    """get_gate_client returns the same instance on repeated calls."""
    monkeypatch.setenv("GATE_URL", "http://test-gate:8000")
    monkeypatch.setenv("L9_NODE_NAME", "test-node")
    client1 = get_gate_client()
    client2 = get_gate_client()
    assert client1 is client2


def test_reset_clears_singleton(monkeypatch):
    """reset_gate_client clears the singleton for reinitialization."""
    monkeypatch.setenv("GATE_URL", "http://test-gate:8000")
    monkeypatch.setenv("L9_NODE_NAME", "test-node")
    client1 = get_gate_client()
    reset_gate_client()
    client2 = get_gate_client()
    assert client1 is not client2
