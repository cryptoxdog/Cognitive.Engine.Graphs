from pathlib import Path
import asyncio

from engine.config.loader import DomainSpecLoader
from engine.graph.driver import GraphDriver
from engine.handlers import handle_admin, handle_match, handle_sync, init_dependencies


SPEC_PATH = Path("domains/plasticos/spec.yaml")


def test_handle_sync_runs_end_to_end() -> None:
    loader = DomainSpecLoader(SPEC_PATH)
    graph = GraphDriver(loader.allowed_canonical_labels())
    init_dependencies(graph_driver=graph, domain_loader=loader)
    result = asyncio.run(
        handle_sync(
            "tenant-a",
            {
                "label": "Buyer",
                "entity": {
                    "entity_id": "buyer-1",
                    "revenue": 0.8,
                    "margin": 0.6,
                    "risk": 0.2,
                    "capacity": 0.9,
                },
            },
        )
    )
    assert result["status"] == "ok"
    assert result["canonical_label"] == "company"
    assert result["packet_type"] == "outcome_event"
    assert graph.nodes["buyer-1"]["label"] == "company"


def test_handle_match_runs_end_to_end() -> None:
    loader = DomainSpecLoader(SPEC_PATH)
    graph = GraphDriver(loader.allowed_canonical_labels())
    init_dependencies(graph_driver=graph, domain_loader=loader)
    result = asyncio.run(
        handle_match(
            "tenant-a",
            {
                "entity_id": "buyer-2",
                "entity_type": "Buyer",
                "revenue": 0.9,
                "margin": 0.8,
                "risk": 0.2,
                "capacity": 0.7,
            },
        )
    )
    assert result["status"] == "ok"
    assert result["decision_packet_type"] == "routing_decision"
    assert result["outcome_packet_type"] == "outcome_event"
    assert result["decision"]["final_decision"] in {"approve", "reject", "defer", "escalate"}


def test_handle_admin_records_outcome() -> None:
    loader = DomainSpecLoader(SPEC_PATH)
    graph = GraphDriver(loader.allowed_canonical_labels())
    init_dependencies(graph_driver=graph, domain_loader=loader)
    result = asyncio.run(
        handle_admin(
            "tenant-a",
            {
                "event_id": "admin-1",
                "entity_id": "buyer-3",
                "entity_type": "Buyer",
                "outcome_state": "success",
            },
        )
    )
    assert result["status"] == "ok"
    assert result["packet_type"] == "outcome_event"
    assert graph.edge_weights[("company", "buyer-3")] == 1.0
