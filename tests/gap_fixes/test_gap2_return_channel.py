"""
Tests for GAP-2: graph_return_channel.py
"""

from __future__ import annotations

import pytest

from engine.contract_enforcement import ContractViolationError
from engine.graph_return_channel import (
    GraphToEnrichReturnChannel,
    build_graph_inference_result_envelope,
)


@pytest.fixture(autouse=True)
def reset_channel() -> None:
    GraphToEnrichReturnChannel.reset_instance()
    yield
    GraphToEnrichReturnChannel.reset_instance()


@pytest.mark.asyncio
async def test_submit_and_drain() -> None:
    envelope = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=[
            {
                "entity_id": "e1",
                "field": "facility_tier",
                "value": "large",
                "confidence": 0.88,
                "rule": "louvain_community_detection",
            }
        ],
    )
    channel = GraphToEnrichReturnChannel.get_instance()
    count = await channel.submit(envelope)
    assert count == 1
    targets = await channel.drain("acme", timeout=0.1)
    assert len(targets) == 1
    assert targets[0].field_name == "facility_tier"
    assert targets[0].source_confidence == 0.88


@pytest.mark.asyncio
async def test_low_confidence_filtered() -> None:
    envelope = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=[{"entity_id": "e1", "field": "x", "value": "v", "confidence": 0.30, "rule": "r1"}],
    )
    channel = GraphToEnrichReturnChannel.get_instance()
    count = await channel.submit(envelope)
    assert count == 0


@pytest.mark.asyncio
async def test_tampered_envelope_rejected() -> None:
    envelope = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=[{"entity_id": "e1", "field": "x", "value": "v", "confidence": 0.9, "rule": "r"}],
    )
    # Tamper with content after hashes are set
    import dataclasses

    tampered = dataclasses.replace(
        envelope,
        inference_outputs=[{"entity_id": "e_TAMPERED"}],
    )
    channel = GraphToEnrichReturnChannel.get_instance()
    with pytest.raises(ContractViolationError):
        await channel.submit(tampered)
