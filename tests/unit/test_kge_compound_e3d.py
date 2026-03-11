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

Unit tests for engine/kge/compound_e3d.py — CompoundE3D model.
Target Coverage: 85%+
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.kge.compound_e3d import CompoundE3D, CompoundE3DConfig

# ============================================================================
# FIXTURES
# ============================================================================

TRAINING_TRIPLES = [
    ("alpha_recycling", "SUPPLIES_TO", "beta_compounding"),
    ("beta_compounding", "SUPPLIES_TO", "gamma_mrf"),
    ("alpha_recycling", "ACCEPTS_POLYMER", "hdpe"),
    ("beta_compounding", "ACCEPTS_POLYMER", "pp"),
    ("gamma_mrf", "ACCEPTS_POLYMER", "hdpe"),
    ("alpha_recycling", "LOCATED_IN", "los_angeles"),
    ("beta_compounding", "LOCATED_IN", "los_angeles"),
    ("gamma_mrf", "LOCATED_IN", "new_york"),
]


@pytest.fixture
def config() -> CompoundE3DConfig:
    """Small config for fast tests."""
    return CompoundE3DConfig(
        embedding_dim=32,
        max_epochs=5,
        negative_sample_size=4,
    )


@pytest.fixture
def trained_model(config: CompoundE3DConfig) -> CompoundE3D:
    """Model trained on test triples."""
    model = CompoundE3D(config)
    with patch("engine.kge.compound_e3d.settings") as mock_settings:
        mock_settings.kge_enabled = True
        model.train(TRAINING_TRIPLES, epochs=3)
    return model


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestCompoundE3DConfig:
    """Test CompoundE3DConfig construction."""

    def test_defaults(self) -> None:
        """Default config has expected values."""
        c = CompoundE3DConfig()
        assert c.embedding_dim == 256
        assert c.learning_rate == 1e-3
        assert c.margin == 1.0

    def test_from_kge_spec(self) -> None:
        """from_kge_spec extracts dim and relations."""
        spec = MagicMock()
        spec.embeddingdim = 128
        spec.trainingrelations = ["REL_A", "REL_B"]
        c = CompoundE3DConfig.from_kge_spec(spec)
        assert c.embedding_dim == 128
        assert c.training_relations == ["REL_A", "REL_B"]

    def test_from_settings(self) -> None:
        """from_settings reads kge_embedding_dim."""
        with patch("engine.kge.compound_e3d.settings") as mock_settings:
            mock_settings.kge_embedding_dim = 512
            c = CompoundE3DConfig.from_settings()
            assert c.embedding_dim == 512


@pytest.mark.unit
class TestCompoundE3DTraining:
    """Test CompoundE3D training."""

    def test_train_skips_when_disabled(self, config: CompoundE3DConfig) -> None:
        """train() skips when kge_enabled=False."""
        model = CompoundE3D(config)
        with patch("engine.kge.compound_e3d.settings") as mock_settings:
            mock_settings.kge_enabled = False
            result = model.train(TRAINING_TRIPLES)
            assert result["status"] == "skipped"
            assert not model._trained

    def test_train_completes(self, config: CompoundE3DConfig) -> None:
        """train() completes and sets _trained=True."""
        model = CompoundE3D(config)
        with patch("engine.kge.compound_e3d.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = model.train(TRAINING_TRIPLES, epochs=3)
            assert result["status"] == "completed"
            assert result["epochs"] == 3
            assert model._trained is True

    def test_train_creates_embeddings(self, config: CompoundE3DConfig) -> None:
        """train() creates entity and relation embeddings."""
        model = CompoundE3D(config)
        with patch("engine.kge.compound_e3d.settings") as mock_settings:
            mock_settings.kge_enabled = True
            model.train(TRAINING_TRIPLES, epochs=2)
            assert len(model._entity_embeddings) >= 6
            assert len(model._relation_embeddings) >= 3

    def test_train_reports_metrics(self, config: CompoundE3DConfig) -> None:
        """train() returns num_entities and num_relations."""
        model = CompoundE3D(config)
        with patch("engine.kge.compound_e3d.settings") as mock_settings:
            mock_settings.kge_enabled = True
            result = model.train(TRAINING_TRIPLES, epochs=1)
            assert result["num_entities"] >= 6
            assert result["num_relations"] >= 3
            assert "final_loss" in result


@pytest.mark.unit
class TestCompoundE3DInference:
    """Test CompoundE3D inference methods."""

    def test_score_triple_untrained_returns_zero(self, config: CompoundE3DConfig) -> None:
        """score_triple returns 0.0 for untrained model."""
        model = CompoundE3D(config)
        assert model.score_triple("a", "r", "b") == 0.0

    def test_score_triple_trained(self, trained_model: CompoundE3D) -> None:
        """score_triple returns value in [0, 1] for trained model."""
        score = trained_model.score_triple("alpha_recycling", "SUPPLIES_TO", "beta_compounding")
        assert 0.0 <= score <= 1.0

    def test_score_triple_unknown_entity(self, trained_model: CompoundE3D) -> None:
        """score_triple returns near-zero for unknown entity."""
        score = trained_model.score_triple("alpha_recycling", "SUPPLIES_TO", "nonexistent")
        assert score < 0.5  # inf distance → low sigmoid score

    def test_embed_known_entity(self, trained_model: CompoundE3D) -> None:
        """embed() returns numpy array for known entity."""
        emb = trained_model.embed("alpha_recycling")
        assert emb is not None
        assert isinstance(emb, np.ndarray)
        assert len(emb) == 32

    def test_embed_unknown_entity(self, trained_model: CompoundE3D) -> None:
        """embed() returns None for unknown entity."""
        assert trained_model.embed("ghost_entity") is None

    def test_predict_tail_untrained(self, config: CompoundE3DConfig) -> None:
        """predict_tail returns empty list for untrained model."""
        model = CompoundE3D(config)
        assert model.predict_tail("a", "r") == []

    def test_predict_tail_trained(self, trained_model: CompoundE3D) -> None:
        """predict_tail returns ranked candidates."""
        results = trained_model.predict_tail(
            "alpha_recycling",
            "SUPPLIES_TO",
            top_k=3,
        )
        assert len(results) <= 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        # Scores should be descending
        if len(results) >= 2:
            assert results[0][1] >= results[1][1]

    def test_predict_tail_with_candidates(self, trained_model: CompoundE3D) -> None:
        """predict_tail respects candidate list."""
        results = trained_model.predict_tail(
            "alpha_recycling",
            "SUPPLIES_TO",
            candidates=["beta_compounding", "gamma_mrf"],
        )
        ids = {r[0] for r in results}
        assert ids.issubset({"beta_compounding", "gamma_mrf"})


@pytest.mark.unit
class TestCompoundE3DSimilarity:
    """Test similarity method."""

    def test_similarity_known_entities(self, trained_model: CompoundE3D) -> None:
        """similarity returns value in [-1, 1]."""
        sim = trained_model.similarity("alpha_recycling", "beta_compounding")
        assert -1.0 <= sim <= 1.0

    def test_similarity_unknown_entity(self, trained_model: CompoundE3D) -> None:
        """similarity returns 0.0 for unknown entity."""
        assert trained_model.similarity("alpha_recycling", "ghost") == 0.0

    def test_similarity_both_unknown(self, config: CompoundE3DConfig) -> None:
        """similarity returns 0.0 when both entities unknown."""
        model = CompoundE3D(config)
        assert model.similarity("a", "b") == 0.0


@pytest.mark.unit
class TestCompoundE3DScores:
    """Test compute_kge_scores batch method."""

    def test_batch_scores(self, trained_model: CompoundE3D) -> None:
        """compute_kge_scores returns dict of scores."""
        scores = trained_model.compute_kge_scores(
            "alpha_recycling",
            "SUPPLIES_TO",
            ["beta_compounding", "gamma_mrf"],
        )
        assert isinstance(scores, dict)
        assert "beta_compounding" in scores
        assert "gamma_mrf" in scores
        assert all(0.0 <= s <= 1.0 for s in scores.values())
