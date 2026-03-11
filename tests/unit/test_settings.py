"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, config]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/config/settings.py — Settings singleton.
Target Coverage: 85%+
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from engine.config.settings import Settings

# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestSettingsDefaults:
    """Test Settings default values."""

    def test_default_env_is_dev(self) -> None:
        """Default environment is dev."""
        s = Settings()
        assert s.l9_env == "dev"
        assert s.is_development is True
        assert s.is_production is False

    def test_default_neo4j_config(self, monkeypatch) -> None:
        """Default Neo4j config uses localhost when no env vars are set."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USERNAME", raising=False)
        monkeypatch.delenv("NEO4J_POOL_SIZE", raising=False)
        s = Settings()
        assert s.neo4j_uri == "bolt://localhost:7687"
        assert s.neo4j_username == "neo4j"
        assert s.neo4j_pool_size == 50

    def test_default_scoring_weights(self) -> None:
        """Default scoring weights are set."""
        s = Settings()
        assert s.w_structural == 0.30
        assert s.w_geo == 0.25
        assert s.w_reinforcement == 0.20
        assert s.w_freshness == 0.10
        assert s.geo_decay_km == 800.0

    def test_default_temporal_decay(self) -> None:
        """Default temporal decay halflives are set."""
        s = Settings()
        assert s.decay_transaction_halflife == 180.0
        assert s.decay_facility_halflife == 90.0
        assert s.decay_structural_halflife == 365.0

    def test_default_kge_config(self) -> None:
        """Default KGE config is disabled."""
        s = Settings()
        assert s.kge_enabled is False
        assert s.kge_embedding_dim == 300
        assert s.kge_confidence_threshold == 0.3

    def test_default_api_config(self) -> None:
        """Default API config is set."""
        s = Settings()
        assert s.api_port == 8000
        assert s.api_workers == 4
        assert s.cors_origins == []

    def test_default_entity_resolution(self) -> None:
        """Default entity resolution config is set."""
        s = Settings()
        assert s.resolution_density_tolerance == 0.05
        assert s.resolution_mfi_tolerance == 5.0
        assert s.resolution_min_confidence == 0.6

    def test_default_feedback_loop(self) -> None:
        """Default outcome EMA alpha is set."""
        s = Settings()
        assert s.outcome_ema_alpha == 0.1


@pytest.mark.unit
class TestSettingsProductionValidation:
    """Test production secret validation."""

    def test_prod_default_neo4j_password_raises(self) -> None:
        """Production mode with default neo4j_password raises ValueError."""
        with pytest.raises(ValueError, match="neo4j_password must be changed"):
            Settings(l9_env="prod", neo4j_password="password", api_secret_key="real-key")

    def test_prod_default_api_secret_raises(self) -> None:
        """Production mode with default api_secret_key raises ValueError."""
        with pytest.raises(ValueError, match="api_secret_key must be changed"):
            Settings(l9_env="prod", neo4j_password="real-pass", api_secret_key="change-me-in-production")

    def test_prod_with_real_secrets_passes(self) -> None:
        """Production mode with real secrets passes validation."""
        s = Settings(l9_env="prod", neo4j_password="s3cur3-p@ss!", api_secret_key="r3al-k3y!")
        assert s.is_production is True

    def test_dev_with_default_secrets_passes(self) -> None:
        """Dev mode with default secrets passes validation."""
        s = Settings(l9_env="dev")
        assert s.is_development is True


@pytest.mark.unit
class TestSettingsProperties:
    """Test computed properties."""

    def test_is_production_true(self) -> None:
        """is_production returns True for prod."""
        s = Settings(l9_env="prod", neo4j_password="real", api_secret_key="real")
        assert s.is_production is True

    def test_is_development_false_in_prod(self) -> None:
        """is_development returns False for prod."""
        s = Settings(l9_env="prod", neo4j_password="real", api_secret_key="real")
        assert s.is_development is False

    def test_is_development_true_in_dev(self) -> None:
        """is_development returns True for dev."""
        s = Settings(l9_env="dev")
        assert s.is_development is True

    def test_is_production_false_in_staging(self) -> None:
        """is_production returns False for staging."""
        s = Settings(l9_env="staging")
        assert s.is_production is False
        assert s.is_development is False


@pytest.mark.unit
class TestSettingsEnvOverride:
    """Test environment variable overrides."""

    def test_env_override_log_level(self) -> None:
        """LOG_LEVEL env var overrides default."""
        with patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
            s = Settings()
            assert s.log_level == "DEBUG"

    def test_env_override_neo4j_uri(self) -> None:
        """NEO4J_URI env var overrides default."""
        with patch.dict("os.environ", {"NEO4J_URI": "bolt://prod:7687"}):
            s = Settings()
            assert s.neo4j_uri == "bolt://prod:7687"

    def test_env_override_max_results(self) -> None:
        """MAX_RESULTS env var overrides default."""
        with patch.dict("os.environ", {"MAX_RESULTS": "50"}):
            s = Settings()
            assert s.max_results == 50
