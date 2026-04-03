"""
Invariant regression tests — Configuration inconsistencies (T5-xx findings).

Verifies that configuration drift fixes from Waves 1-4 remain in place.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.finding("T5-01")
class TestT501KGEDimensionConsistency:
    """T5-01: KGE embedding dimension must be consistent across settings and schema."""

    def test_settings_kge_dim_matches_schema(self):
        """settings.kge_embedding_dim must equal KGESpec default."""
        from engine.config.schema import KGESpec
        from engine.config.settings import Settings

        s = Settings()
        kge = KGESpec()
        assert s.kge_embedding_dim == kge.embeddingdim, (
            f"Settings kge_embedding_dim={s.kge_embedding_dim} != KGESpec.embeddingdim={kge.embeddingdim}"
        )


@pytest.mark.finding("T5-02")
class TestT502EdgeSpecAlias:
    """T5-02: EdgeSpec.from_ alias must work correctly with Pydantic."""

    def test_edge_spec_from_alias(self):
        """EdgeSpec accepts 'from' as alias for 'from_'."""
        from engine.config.schema import (
            EdgeCategory,
            EdgeDirection,
            EdgeSpec,
            ManagedByType,
        )

        edge = EdgeSpec(
            type="TEST",
            **{"from": "NodeA"},
            to="NodeB",
            direction=EdgeDirection.DIRECTED,
            category=EdgeCategory.CAPABILITY,
            managedby=ManagedByType.SYNC,
        )
        assert edge.from_ == "NodeA"


@pytest.mark.finding("T5-03")
class TestT503ChassisImportContract:
    """T5-03: Chassis should minimize engine imports."""

    def test_engine_does_not_import_chassis_except_allowed(self):
        """Only engine/handlers.py and engine/boot.py may import from chassis."""
        engine_dir = ROOT / "engine"
        allowed = {"handlers.py", "boot.py"}
        for f in engine_dir.rglob("*.py"):
            if f.name in allowed and f.parent == engine_dir:
                continue
            content = f.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if re.match(r"^(from|import)\s+chassis\b", stripped):
                    pytest.fail(f"T5-03: {f.relative_to(ROOT)} imports chassis — only {allowed} may do this")


@pytest.mark.finding("T5-04")
class TestT504ScoringBlocklistConsistency:
    """T5-04: Scoring assembler blocklist must be consistent with compiler output."""

    def test_dangerous_keywords_defined(self):
        """ScoringAssembler defines dangerous Cypher keywords."""
        from engine.scoring.assembler import _DANGEROUS_CYPHER_KEYWORDS

        assert "create" in _DANGEROUS_CYPHER_KEYWORDS
        assert "delete" in _DANGEROUS_CYPHER_KEYWORDS
        assert "merge" in _DANGEROUS_CYPHER_KEYWORDS
        assert "call" in _DANGEROUS_CYPHER_KEYWORDS

    def test_custom_expression_validation_blocks_keywords(self):
        """_validate_custom_expression rejects dangerous keywords."""
        from engine.scoring.assembler import _validate_custom_expression

        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_custom_expression("CALL db.labels()", "test_dim")
        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_custom_expression("CREATE (n:Node)", "test_dim")


class TestWave1Settings:
    """Verify Wave 1 settings are present and have correct defaults."""

    def test_wave1_settings_exist(self):
        from engine.config.settings import Settings

        s = Settings()
        assert hasattr(s, "domain_strict_validation")
        assert hasattr(s, "score_clamp_enabled")
        assert hasattr(s, "strict_null_gates")
        assert hasattr(s, "max_hop_hard_cap")
        assert hasattr(s, "param_strict_mode")

    def test_wave1_defaults(self):
        from engine.config.settings import Settings

        s = Settings()
        assert s.domain_strict_validation is True
        assert s.score_clamp_enabled is True
        assert s.strict_null_gates is True
        assert s.max_hop_hard_cap == 10
        assert s.param_strict_mode is True

    def test_wave2_settings_exist(self):
        from engine.config.settings import Settings

        s = Settings()
        assert hasattr(s, "feedback_enabled")
        assert hasattr(s, "confidence_check_enabled")
        assert hasattr(s, "monoculture_threshold")
        assert hasattr(s, "score_normalize")

    def test_production_secret_validation(self):
        """Production mode rejects default secrets."""
        from engine.config.settings import Settings

        with pytest.raises(Exception):
            Settings(l9_env="prod", neo4j_password="password", api_secret_key="change-me-in-production")
