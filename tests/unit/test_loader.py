from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SPEC_PATH = Path("domains/plasticos/spec.yaml")


def _canonical_bindings() -> dict[str, str]:
    raw = yaml.safe_load(SPEC_PATH.read_text())
    return {node["label"]: node["canonical"] for node in raw["ontology"]["nodes"]}


def test_loader_builds_semantic_bindings() -> None:
    bindings = _canonical_bindings()
    assert bindings["Buyer"] == "company"
    assert bindings["Contact"] == "person"


def test_loader_rejects_unknown_label() -> None:
    bindings = _canonical_bindings()
    with pytest.raises(KeyError):
        _ = bindings["Unknown"]
