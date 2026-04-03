"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, hgkr, gds, dag]
owner: engine-team
status: active
--- /L9_META ---

Tests for HGKR-inspired GDS DAG execution pipeline.

Validates topological ordering, cycle detection, and backward
compatibility of the iterative GDS execution pipeline.

Reference:
    HGKR iterative cross-graph propagation:
    Layer L output feeds Layer L+1 input.
"""

from __future__ import annotations

import pytest

from engine.config.schema import GDSJobScheduleSpec, GDSJobSpec, GDSProjectionSpec
from engine.gds.scheduler import GDSScheduler


def _make_job(algorithm: str, depends_on: list[str] | None = None, **kwargs: object) -> GDSJobSpec:
    """Create a GDSJobSpec for testing DAG ordering."""
    return GDSJobSpec(
        name=f"job_{algorithm}",
        algorithm=algorithm,
        schedule=GDSJobScheduleSpec(type="manual"),
        projection=GDSProjectionSpec(nodelabels=["Facility"], edgetypes=["SUPPLIES_TO"]),
        depends_on=depends_on or [],
        **kwargs,
    )


@pytest.mark.unit
class TestDAGExecution:
    """Validate GDS DAG topological ordering."""

    def test_empty_jobs(self) -> None:
        """No jobs -> no waves."""
        waves = GDSScheduler._build_execution_dag([])
        assert waves == []

    def test_single_job_no_deps(self) -> None:
        """Single job -> single wave."""
        jobs = [_make_job("louvain")]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 1
        assert waves[0][0].algorithm == "louvain"

    def test_parallel_no_deps(self) -> None:
        """Multiple jobs without deps -> all in wave 0 (parallel)."""
        jobs = [_make_job("louvain"), _make_job("geoproximity"), _make_job("temporalrecency")]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 1
        assert len(waves[0]) == 3

    def test_linear_chain(self) -> None:
        """louvain -> cooccurrence -> reinforcement = 3 sequential waves."""
        jobs = [
            _make_job("louvain"),
            _make_job("cooccurrence", ["louvain"]),
            _make_job("reinforcement", ["cooccurrence"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 3
        assert waves[0][0].algorithm == "louvain"
        assert waves[1][0].algorithm == "cooccurrence"
        assert waves[2][0].algorithm == "reinforcement"

    def test_diamond_dependency(self) -> None:
        """Diamond: louvain -> {cooccurrence, geoproximity} -> reinforcement."""
        jobs = [
            _make_job("louvain"),
            _make_job("cooccurrence", ["louvain"]),
            _make_job("geoproximity", ["louvain"]),
            _make_job("reinforcement", ["cooccurrence", "geoproximity"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 3

        # Wave 0: louvain
        assert len(waves[0]) == 1
        assert waves[0][0].algorithm == "louvain"

        # Wave 1: cooccurrence + geoproximity (parallel)
        wave1_algs = {j.algorithm for j in waves[1]}
        assert wave1_algs == {"cooccurrence", "geoproximity"}

        # Wave 2: reinforcement
        assert len(waves[2]) == 1
        assert waves[2][0].algorithm == "reinforcement"

    def test_partial_dependencies(self) -> None:
        """Some jobs have deps, others don't. Independent jobs in wave 0."""
        jobs = [
            _make_job("louvain"),
            _make_job("geoproximity"),  # independent
            _make_job("cooccurrence", ["louvain"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 2

        # Wave 0: louvain + geoproximity (parallel)
        wave0_algs = {j.algorithm for j in waves[0]}
        assert wave0_algs == {"louvain", "geoproximity"}

        # Wave 1: cooccurrence
        assert waves[1][0].algorithm == "cooccurrence"

    def test_circular_dependency_handled(self) -> None:
        """Circular deps don't hang -- cycle members placed in fallback wave."""
        jobs = [
            _make_job("a", ["b"]),
            _make_job("b", ["a"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        total = sum(len(w) for w in waves)
        assert total == 2  # Both jobs placed somewhere

    def test_circular_with_valid_chain(self) -> None:
        """Mix of valid chain + cycle: valid jobs ordered, cycle in fallback."""
        jobs = [
            _make_job("louvain"),
            _make_job("cooccurrence", ["louvain"]),
            _make_job("x", ["y"]),  # cycle
            _make_job("y", ["x"]),  # cycle
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        total = sum(len(w) for w in waves)
        assert total == 4

        # First wave should contain louvain (the root of valid chain)
        wave0_algs = {j.algorithm for j in waves[0]}
        assert "louvain" in wave0_algs

    def test_unknown_dependency_ignored(self) -> None:
        """depends_on referencing non-existent job -> treated as no dependency."""
        jobs = [
            _make_job("louvain"),
            _make_job("cooccurrence", ["nonexistent_algorithm"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        # Both in wave 0 since the dependency is to a non-existent job
        assert len(waves) == 1
        assert len(waves[0]) == 2

    def test_backward_compatible_no_depends_on(self) -> None:
        """Jobs without depends_on field -> all in wave 0 (original behavior).

        This is the critical backward compatibility test: existing domain
        specs that don't use depends_on must execute identically to
        pre-enhancement behavior.
        """
        jobs = [
            _make_job("louvain"),
            _make_job("cooccurrence"),
            _make_job("reinforcement"),
            _make_job("temporalrecency"),
            _make_job("geoproximity"),
            _make_job("equipmentsync"),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 1
        assert len(waves[0]) == 6  # All 6 in parallel -- same as before

    def test_all_jobs_in_output(self) -> None:
        """Every input job appears exactly once in output waves."""
        jobs = [
            _make_job("a"),
            _make_job("b", ["a"]),
            _make_job("c", ["a"]),
            _make_job("d", ["b", "c"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        all_placed = [j.algorithm for w in waves for j in w]
        assert sorted(all_placed) == ["a", "b", "c", "d"]
        assert len(all_placed) == len(set(all_placed))  # No duplicates

    def test_self_dependency_creates_cycle(self) -> None:
        """A job depending on itself is a cycle."""
        jobs = [_make_job("a", ["a"])]
        waves = GDSScheduler._build_execution_dag(jobs)
        total = sum(len(w) for w in waves)
        assert total == 1  # Job still placed (in fallback wave)

    def test_deep_chain(self) -> None:
        """Deep dependency chain: a -> b -> c -> d -> e = 5 waves."""
        jobs = [
            _make_job("a"),
            _make_job("b", ["a"]),
            _make_job("c", ["b"]),
            _make_job("d", ["c"]),
            _make_job("e", ["d"]),
        ]
        waves = GDSScheduler._build_execution_dag(jobs)
        assert len(waves) == 5
        for i, expected_alg in enumerate(["a", "b", "c", "d", "e"]):
            assert waves[i][0].algorithm == expected_alg
