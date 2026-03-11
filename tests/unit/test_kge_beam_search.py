"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, kge]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/kge/beam_search.py — BeamSearchEngine.
Target Coverage: 85%+
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from engine.kge.beam_search import (
    BeamCandidate,
    BeamSearchConfig,
    BeamSearchEngine,
    PruneStrategy,
)
from engine.kge.compound_e3d import CompoundE3D, CompoundE3DConfig
from engine.kge.transformations import Scale

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def model() -> CompoundE3D:
    """Create a minimal CompoundE3D model."""
    return CompoundE3D(CompoundE3DConfig(embedding_dim=64))


@pytest.fixture
def config() -> BeamSearchConfig:
    """Create a beam search config with small dimensions for testing."""
    return BeamSearchConfig(
        beam_width=3,
        max_depth=2,
        prune_strategy=PruneStrategy.SCORE_THRESHOLD,
        score_threshold=0.3,
    )


@pytest.fixture
def engine(model: CompoundE3D, config: BeamSearchConfig) -> BeamSearchEngine:
    """Create a BeamSearchEngine."""
    return BeamSearchEngine(model=model, config=config)


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestBeamCandidate:
    """Test BeamCandidate dataclass."""

    def test_to_dict_serialization(self) -> None:
        """to_dict returns all fields."""
        c = BeamCandidate(
            transformation_id="var_0001",
            transformation_type="rotation",
            params={"angle": 45.0},
            score=0.85,
            depth=1,
            parent_id="var_0000",
        )
        d = c.to_dict()
        assert d["id"] == "var_0001"
        assert d["type"] == "rotation"
        assert d["score"] == pytest.approx(0.85)
        assert d["depth"] == 1
        assert d["parent_id"] == "var_0000"

    def test_ordering_by_score_desc(self) -> None:
        """BeamCandidates sort by score descending via __lt__."""
        a = BeamCandidate("a", "r", {}, score=0.9, depth=1)
        b = BeamCandidate("b", "r", {}, score=0.7, depth=1)
        assert a < b  # higher score sorts first (negated)

    def test_ordering_tiebreak_by_id(self) -> None:
        """Equal scores tiebreak by transformation_id."""
        a = BeamCandidate("a", "r", {}, score=0.8, depth=1)
        b = BeamCandidate("b", "r", {}, score=0.8, depth=1)
        assert a < b  # "a" < "b" lexically


@pytest.mark.unit
class TestBeamSearchConfig:
    """Test BeamSearchConfig."""

    def test_defaults(self) -> None:
        """Default config has sensible values."""
        c = BeamSearchConfig()
        assert c.beam_width == 5
        assert c.max_depth == 3
        assert c.prune_strategy == PruneStrategy.COMBINED

    def test_from_spec_with_none(self) -> None:
        """from_spec(None) returns defaults."""
        c = BeamSearchConfig.from_spec(None)
        assert c.beam_width == 5

    def test_from_spec_with_spec(self) -> None:
        """from_spec extracts beamwidth and maxdepth."""
        spec = MagicMock()
        spec.beamwidth = 10
        spec.maxdepth = 5
        c = BeamSearchConfig.from_spec(spec)
        assert c.beam_width == 10
        assert c.max_depth == 5


@pytest.mark.unit
class TestBeamSearchEngine:
    """Test BeamSearchEngine execution."""

    def test_search_skips_when_kge_disabled(self, model: CompoundE3D) -> None:
        """search() returns skipped when kge_enabled=False."""
        config = BeamSearchConfig(beam_width=3, max_depth=1)
        engine = BeamSearchEngine(model, config)
        with patch("engine.kge.beam_search.settings") as mock_settings:
            mock_settings.kge_enabled = False
            result = engine.search()
            assert result["status"] == "skipped"
            assert result["variants"] == []

    def test_search_returns_variants(self, model: CompoundE3D) -> None:
        """search() returns variant dicts when kge_enabled=True."""
        config = BeamSearchConfig(
            beam_width=3,
            max_depth=1,
            prune_strategy=PruneStrategy.SCORE_THRESHOLD,
            score_threshold=0.0,
        )
        engine = BeamSearchEngine(model, config)
        with patch("engine.kge.beam_search.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = engine.search()
            assert "variants" in result
            assert len(result["variants"]) <= config.beam_width
            assert "depth_levels" in result
            assert "audit_trail" in result

    def test_search_audit_trail_length(self, model: CompoundE3D) -> None:
        """Audit trail has one entry per depth level."""
        config = BeamSearchConfig(beam_width=3, max_depth=2, score_threshold=0.0)
        engine = BeamSearchEngine(model, config)
        with patch("engine.kge.beam_search.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = engine.search()
            assert len(result["audit_trail"]) == config.max_depth

    def test_search_config_snapshot(self, model: CompoundE3D) -> None:
        """search() includes config snapshot in result."""
        config = BeamSearchConfig(beam_width=5, max_depth=2, score_threshold=0.4)
        engine = BeamSearchEngine(model, config)
        with patch("engine.kge.beam_search.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = engine.search()
            sc = result["search_config"]
            assert sc["beam_width"] == 5
            assert sc["max_depth"] == 2
            assert sc["score_threshold"] == pytest.approx(0.4)

    def test_pruned_candidates_logged(self, model: CompoundE3D) -> None:
        """Pruned candidates are logged when log_pruned=True."""
        config = BeamSearchConfig(
            beam_width=2,
            max_depth=1,
            prune_strategy=PruneStrategy.SCORE_THRESHOLD,
            score_threshold=0.5,
            log_pruned=True,
        )
        engine = BeamSearchEngine(model, config)
        with patch("engine.kge.beam_search.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = engine.search()
            # Some candidates should be pruned since threshold is 0.5
            assert "pruned" in result


@pytest.mark.unit
class TestPruneStrategies:
    """Test individual pruning strategies."""

    def test_prune_by_threshold(self, engine: BeamSearchEngine) -> None:
        """_prune_by_threshold keeps candidates above threshold."""
        candidates = [
            BeamCandidate("a", "r", {}, score=0.8, depth=1),
            BeamCandidate("b", "r", {}, score=0.2, depth=1),
            BeamCandidate("c", "r", {}, score=0.5, depth=1),
        ]
        kept = engine._prune_by_threshold(candidates)
        assert len(kept) == 2
        scores = {c.transformation_id for c in kept}
        assert "a" in scores
        assert "c" in scores
        assert "b" not in scores

    def test_prune_by_diversity(self, engine: BeamSearchEngine) -> None:
        """_prune_by_diversity filters similar candidates."""
        c1 = BeamCandidate("a", "r", {"angle": 45.0}, score=0.9, depth=1)
        c2 = BeamCandidate("b", "r", {"angle": 45.001}, score=0.85, depth=1)
        c3 = BeamCandidate("c", "r", {"angle": 180.0}, score=0.7, depth=1)
        engine.config.diversity_threshold = 0.9
        kept = engine._prune_by_diversity([c1, c2, c3])
        assert len(kept) >= 1
        assert kept[0].transformation_id == "a"

    def test_prune_by_constraint(self, engine: BeamSearchEngine) -> None:
        """_prune_by_constraint filters invalid transformations."""
        engine.config.constraint_validators = [lambda tx: isinstance(tx, Scale)]
        candidates = [
            BeamCandidate(
                "a", "rotation", {"angle": 45.0, "axis_x": 1.0, "axis_y": 0.0, "axis_z": 0.0}, score=0.9, depth=1
            ),
            BeamCandidate("b", "scale", {"factor": 1.5}, score=0.8, depth=1),
        ]
        kept = engine._prune_by_constraint(candidates)
        assert len(kept) == 1
        assert kept[0].transformation_id == "b"

    def test_prune_by_constraint_no_validators(self, engine: BeamSearchEngine) -> None:
        """_prune_by_constraint passes all when no validators."""
        engine.config.constraint_validators = []
        candidates = [
            BeamCandidate("a", "r", {}, score=0.9, depth=1),
        ]
        kept = engine._prune_by_constraint(candidates)
        assert len(kept) == 1


@pytest.mark.unit
class TestParamSimilarity:
    """Test _param_similarity static method."""

    def test_identical_params(self) -> None:
        """Identical params give similarity 1.0."""
        sim = BeamSearchEngine._param_similarity({"a": 1.0}, {"a": 1.0})
        assert sim == pytest.approx(1.0)

    def test_different_params(self) -> None:
        """Different params give similarity < 1.0."""
        sim = BeamSearchEngine._param_similarity({"a": 0.0}, {"a": 100.0})
        assert sim < 0.1

    def test_empty_params(self) -> None:
        """Empty params give similarity 1.0."""
        sim = BeamSearchEngine._param_similarity({}, {})
        assert sim == pytest.approx(1.0)


@pytest.mark.unit
class TestSuccessorGeneration:
    """Test successor generation."""

    def test_generates_successors(self, engine: BeamSearchEngine) -> None:
        """_generate_successors produces successor candidates."""
        parent = BeamCandidate("p", "identity", {}, score=1.0, depth=0)
        successors = engine._generate_successors(parent)
        assert len(successors) > 0
        assert all(s.depth == 1 for s in successors)
        assert all(s.parent_id == "p" for s in successors)

    def test_successor_types(self, engine: BeamSearchEngine) -> None:
        """Successors include all transformation types."""
        parent = BeamCandidate("p", "identity", {}, score=1.0, depth=0)
        successors = engine._generate_successors(parent)
        types = {s.transformation_type for s in successors}
        assert types == {"rotation", "scale", "translation", "flip", "hyperplane"}

    def test_build_unknown_type_raises(self, engine: BeamSearchEngine) -> None:
        """_build_transformation raises on unknown type."""
        with pytest.raises(ValueError, match="Unknown transformation type"):
            engine._build_transformation("warp", {"factor": 1.0})
