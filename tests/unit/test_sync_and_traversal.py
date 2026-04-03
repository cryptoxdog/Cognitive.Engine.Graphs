from __future__ import annotations

from pathlib import Path

import yaml

SPEC_PATH = Path("domains/plasticos/spec.yaml")


def _raw_spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text())


def test_sync_spec_maps_buyer_to_canonical_company() -> None:
    raw = _raw_spec()
    bindings = {node["label"]: node["canonical"] for node in raw["ontology"]["nodes"]}
    assert bindings["Buyer"] == "company"


def test_traversal_step_references_declared_labels_and_edge_types() -> None:
    raw = _raw_spec()
    node_labels = {node["label"] for node in raw["ontology"]["nodes"]}
    edge_types = {edge["type"] for edge in raw["ontology"]["edges"]}
    step = raw["traversal"]["steps"][0]

    assert step["node_label"] in node_labels
    assert step["relationship_type"] in edge_types
