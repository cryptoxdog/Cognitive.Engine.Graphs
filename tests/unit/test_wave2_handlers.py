"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, handlers, wave2]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for Wave 2 handler integrations.
Tests admin subactions (calibration_run, score_feedback, apply_weight_proposal)
and the outcome sync type.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.handlers import handle_admin, handle_sync, init_dependencies


def _make_graph_driver() -> MagicMock:
    driver = MagicMock()
    driver.execute_query = AsyncMock(return_value=[])
    return driver


def _make_domain_loader(spec: MagicMock | None = None) -> MagicMock:
    loader = MagicMock()
    if spec is None:
        spec = MagicMock()
        spec.domain.id = "test_domain"
        spec.calibration = None
        spec.sync = None
    loader.load_domain.return_value = spec
    loader.list_domains.return_value = ["test_domain"]
    return loader


@pytest.mark.unit
class TestCalibrationRunSubaction:
    """Test the calibration_run admin subaction."""

    @pytest.mark.asyncio
    async def test_calibration_run_no_spec(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        result = await handle_admin("test_tenant", {
            "subaction": "calibration_run",
            "domain_id": "test_domain",
        })

        assert result["status"] == "no_calibration_spec"
        assert result["total_pairs"] == 0

    @pytest.mark.asyncio
    async def test_calibration_run_with_spec(self):
        from engine.config.schema import CalibrationPair, CalibrationSpec

        spec = MagicMock()
        spec.domain.id = "test_domain"
        spec.calibration = CalibrationSpec(
            pairs=[
                CalibrationPair(node_a="A", node_b="B", expected_score_min=0.3, expected_score_max=0.7),
            ],
            weight_set="default",
        )

        driver = _make_graph_driver()
        loader = _make_domain_loader(spec)
        init_dependencies(driver, loader)

        result = await handle_admin("test_tenant", {
            "subaction": "calibration_run",
            "domain_id": "test_domain",
        })

        assert result["status"] == "calibration_spec_loaded"
        assert result["total_pairs"] == 1


@pytest.mark.unit
class TestScoreFeedbackSubaction:
    """Test the score_feedback admin subaction."""

    @pytest.mark.asyncio
    async def test_feedback_disabled(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        with patch("engine.handlers._fb_settings", create=True):
            with patch("engine.config.settings.Settings") as mock_cls:
                result = await handle_admin("test_tenant", {
                    "subaction": "score_feedback",
                    "domain_id": "test_domain",
                })
                # By default feedback_enabled=False
                assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_feedback_enabled(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.feedback_enabled = True
            result = await handle_admin("test_tenant", {
                "subaction": "score_feedback",
                "domain_id": "test_domain",
            })

            assert result["status"] == "feedback_computed"
            assert "sample_count" in result


@pytest.mark.unit
class TestApplyWeightProposal:
    """Test the apply_weight_proposal admin subaction."""

    @pytest.mark.asyncio
    async def test_apply_disabled(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        result = await handle_admin("test_tenant", {
            "subaction": "apply_weight_proposal",
            "proposed_weights": {"geo": 0.02},
            "current_weights": {"geo": 0.25},
        })
        # Default: feedback_enabled=False
        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_apply_enabled(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.feedback_enabled = True
            result = await handle_admin("test_tenant", {
                "subaction": "apply_weight_proposal",
                "proposed_weights": {"geo": 0.02},
                "current_weights": {"geo": 0.25},
            })

            assert result["status"] == "weights_applied"
            assert result["new_weights"]["geo"] == pytest.approx(0.27, abs=0.001)


@pytest.mark.unit
class TestOutcomeSyncType:
    """Test the outcome sync type (W2-02)."""

    @pytest.mark.asyncio
    async def test_outcome_sync_disabled(self):
        """When feedback_enabled=False, outcome sync should fall through to normal sync."""
        driver = _make_graph_driver()
        spec = MagicMock()
        spec.domain.id = "test_domain"
        spec.sync = None
        loader = _make_domain_loader(spec)
        init_dependencies(driver, loader)

        # With feedback disabled, "outcome" entity_type goes to normal sync path
        # which requires sync endpoints configured -> should raise
        from engine.handlers import ValidationError

        with pytest.raises(ValidationError, match="No sync endpoints configured"):
            await handle_sync("test_tenant", {
                "entity_type": "outcome",
                "batch": [{"match_id": "m1", "chosen_candidate_id": "c1", "outcome": "positive"}],
            })

    @pytest.mark.asyncio
    async def test_outcome_sync_enabled(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.feedback_enabled = True
            result = await handle_sync("test_tenant", {
                "entity_type": "outcome",
                "batch": [
                    {"match_id": "m1", "chosen_candidate_id": "c1", "outcome": "positive"},
                    {"match_id": "m2", "chosen_candidate_id": "c2", "outcome": "negative"},
                ],
            })

            assert result["status"] == "success"
            assert result["entity_type"] == "outcome"
            assert result["synced_count"] == 2

    @pytest.mark.asyncio
    async def test_outcome_sync_invalid_outcome_skipped(self):
        driver = _make_graph_driver()
        loader = _make_domain_loader()
        init_dependencies(driver, loader)

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.feedback_enabled = True
            result = await handle_sync("test_tenant", {
                "entity_type": "outcome",
                "batch": [
                    {"match_id": "m1", "chosen_candidate_id": "c1", "outcome": "invalid"},
                    {"match_id": "m2", "chosen_candidate_id": "c2", "outcome": "positive"},
                ],
            })

            assert result["synced_count"] == 1  # only the valid one
