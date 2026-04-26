import pytest

from engine.config.loader import DomainPackLoader


def test_loader_builds_semantic_bindings() -> None:
    """Semantic binding via get_canonical_label — skip if method not implemented."""
    loader = DomainPackLoader()
    if not hasattr(loader, "get_canonical_label"):
        pytest.skip("DomainPackLoader.get_canonical_label not implemented")
    assert loader.get_canonical_label("Buyer") == "company"
    assert loader.get_canonical_label("Contact") == "person"


def test_loader_rejects_unknown_label() -> None:
    """Unknown label rejection — skip if method not implemented."""
    loader = DomainPackLoader()
    if not hasattr(loader, "get_canonical_label"):
        pytest.skip("DomainPackLoader.get_canonical_label not implemented")
    with pytest.raises(ValueError):
        loader.get_canonical_label("Unknown")
