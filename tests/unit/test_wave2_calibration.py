"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, calibration, wave2]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for W2-01: Score Calibration Framework.
Tests calibration report, forward simulation NDCG, Kendall-tau, drift detection.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from engine.config.schema import CalibrationPair, CalibrationSpec
from engine.scoring.calibration import (
    CalibrationReport,
    DriftReport,
    ForwardSimReport,
    ScoreCalibrator,
)


def _make_domain_spec(calibration: CalibrationSpec | None = None) -> MagicMock:
    spec = MagicMock()
    spec.domain.id = "test_domain"
    spec.calibration = calibration
    return spec


@pytest.mark.unit
class TestCalibrationPairModel:
    """Test CalibrationPair Pydantic validation."""

    def test_valid_pair(self):
        pair = CalibrationPair(
            node_a="A", node_b="B", expected_score_min=0.3, expected_score_max=0.7
        )
        assert pair.node_a == "A"
        assert pair.expected_score_min == 0.3

    def test_pair_min_greater_than_max_raises(self):
        with pytest.raises(ValueError, match="expected_score_min"):
            CalibrationPair(
                node_a="A", node_b="B", expected_score_min=0.8, expected_score_max=0.3
            )

    def test_pair_with_label(self):
        pair = CalibrationPair(
            node_a="X", node_b="Y", expected_score_min=0.0, expected_score_max=1.0, label="test_pair"
        )
        assert pair.label == "test_pair"


@pytest.mark.unit
class TestRunCalibration:
    """Test ScoreCalibrator.run_calibration()."""

    def test_all_pairs_pass(self):
        pairs = [
            CalibrationPair(node_a="A", node_b="B", expected_score_min=0.5, expected_score_max=0.9),
            CalibrationPair(node_a="C", node_b="D", expected_score_min=0.2, expected_score_max=0.6),
        ]
        actual_scores = {("A", "B"): 0.7, ("C", "D"): 0.4}
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.run_calibration(pairs, actual_scores)

        assert isinstance(report, CalibrationReport)
        assert report.overall_pass is True
        assert report.passed == 2
        assert report.failed == 0

    def test_pair_out_of_range_fails(self):
        pairs = [
            CalibrationPair(node_a="A", node_b="B", expected_score_min=0.5, expected_score_max=0.7),
        ]
        actual_scores = {("A", "B"): 0.3}  # below min
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.run_calibration(pairs, actual_scores)

        assert report.overall_pass is False
        assert report.failed == 1
        assert report.results[0].diff == pytest.approx(0.2, abs=0.001)

    def test_missing_score_fails(self):
        pairs = [
            CalibrationPair(node_a="A", node_b="B", expected_score_min=0.3, expected_score_max=0.7),
        ]
        actual_scores = {}  # no score
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.run_calibration(pairs, actual_scores)

        assert report.overall_pass is False
        assert report.results[0].actual_score is None
        assert report.results[0].diff == -1.0

    def test_empty_pairs(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.run_calibration([], {})
        assert report.overall_pass is True
        assert report.total_pairs == 0

    def test_score_above_max(self):
        pairs = [
            CalibrationPair(node_a="A", node_b="B", expected_score_min=0.3, expected_score_max=0.5),
        ]
        actual_scores = {("A", "B"): 0.8}  # above max
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.run_calibration(pairs, actual_scores)

        assert report.overall_pass is False
        assert report.results[0].diff == pytest.approx(0.3, abs=0.001)


@pytest.mark.unit
class TestForwardSimulation:
    """Test ScoreCalibrator.forward_simulate()."""

    def test_perfect_ranking(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        abstract = ["A", "B", "C", "D"]
        concrete = ["A", "B", "C", "D"]
        report = calibrator.forward_simulate(abstract, concrete)

        assert isinstance(report, ForwardSimReport)
        assert report.ndcg == pytest.approx(1.0, abs=0.001)
        assert report.kendall_tau == pytest.approx(1.0, abs=0.001)
        assert report.diverged is False
        assert report.misranked_pairs == []

    def test_reversed_ranking(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        abstract = ["A", "B", "C", "D"]
        concrete = ["D", "C", "B", "A"]
        report = calibrator.forward_simulate(abstract, concrete)

        assert report.kendall_tau == pytest.approx(-1.0, abs=0.001)
        assert report.diverged is True
        assert len(report.misranked_pairs) > 0

    def test_partial_overlap(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        abstract = ["A", "B", "C"]
        concrete = ["A", "C", "D"]  # D not in abstract, B missing
        report = calibrator.forward_simulate(abstract, concrete)

        assert 0.0 <= report.ndcg <= 1.0
        assert -1.0 <= report.kendall_tau <= 1.0

    def test_empty_abstract(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.forward_simulate([], ["A", "B"])

        assert report.ndcg == 0.0
        assert report.diverged is True

    def test_empty_concrete(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.forward_simulate(["A", "B"], [])

        assert report.ndcg == 0.0
        assert report.diverged is True

    def test_single_element(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.forward_simulate(["A"], ["A"])

        assert report.ndcg == pytest.approx(1.0, abs=0.001)
        assert report.diverged is False


@pytest.mark.unit
class TestScoreDrift:
    """Test ScoreCalibrator.detect_score_drift()."""

    def test_no_drift(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        baseline = [0.50, 0.55, 0.52, 0.53, 0.54]
        current = [0.51, 0.54, 0.53, 0.52, 0.55]
        report = calibrator.detect_score_drift(baseline, current)

        assert isinstance(report, DriftReport)
        assert report.drift_detected is False

    def test_significant_drift(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        baseline = [0.2, 0.3, 0.25, 0.22]
        current = [0.8, 0.9, 0.85, 0.88]
        report = calibrator.detect_score_drift(baseline, current)

        assert report.drift_detected is True
        assert report.delta_mean > 0.4

    def test_empty_baseline(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.detect_score_drift([], [0.5, 0.6])

        assert report.drift_detected is True
        assert report.ks_statistic == 1.0

    def test_empty_current(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        report = calibrator.detect_score_drift([0.5, 0.6], [])

        assert report.drift_detected is True

    def test_identical_distributions(self):
        spec = _make_domain_spec()
        calibrator = ScoreCalibrator(spec)
        scores = [0.3, 0.5, 0.7, 0.4, 0.6]
        report = calibrator.detect_score_drift(scores, list(scores))

        assert report.drift_detected is False
        assert report.ks_statistic == pytest.approx(0.0, abs=0.001)
        assert report.delta_mean == pytest.approx(0.0, abs=0.001)


@pytest.mark.unit
class TestCalibrationReport:
    """Test ScoreCalibrator.generate_calibration_report()."""

    def test_no_calibration_spec(self):
        spec = _make_domain_spec(calibration=None)
        calibrator = ScoreCalibrator(spec)
        report = calibrator.generate_calibration_report("test_domain")

        assert report["status"] == "no_calibration_spec"
        assert report["total_pairs"] == 0

    def test_with_calibration_spec(self):
        cal = CalibrationSpec(
            pairs=[
                CalibrationPair(node_a="A", node_b="B", expected_score_min=0.3, expected_score_max=0.7),
            ],
            weight_set="default",
        )
        spec = _make_domain_spec(calibration=cal)
        calibrator = ScoreCalibrator(spec)
        report = calibrator.generate_calibration_report("test_domain")

        assert report["status"] == "calibration_spec_loaded"
        assert report["total_pairs"] == 1
        assert report["weight_set"] == "default"

    def test_empty_pairs_in_spec(self):
        cal = CalibrationSpec(pairs=[])
        spec = _make_domain_spec(calibration=cal)
        calibrator = ScoreCalibrator(spec)
        report = calibrator.generate_calibration_report("test_domain")

        assert report["status"] == "no_calibration_spec"
