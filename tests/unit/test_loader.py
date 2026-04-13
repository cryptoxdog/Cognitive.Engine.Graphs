from pathlib import Path

import pytest

from engine.config.loader import DomainPackLoader as DomainSpecLoader

SPEC_PATH = Path("domains/plasticos/spec.yaml")


def test_loader_builds_semantic_bindings() -> None:
    loader = DomainSpecLoader(SPEC_PATH)
    assert loader.get_canonical_label("Buyer") == "company"
    assert loader.get_canonical_label("Contact") == "person"


def test_loader_rejects_unknown_label() -> None:
    loader = DomainSpecLoader(SPEC_PATH)
    with pytest.raises(ValueError):
        loader.get_canonical_label("Unknown")
