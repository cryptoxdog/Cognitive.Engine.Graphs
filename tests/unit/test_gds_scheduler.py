"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, gds]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.gds.scheduler — GDSScheduler.

Covers:
- Job registration (cron + manual)
- Algorithm dispatch (louvain, cooccurrence, reinforcement, temporalrecency,
  geoproximity, equipmentsync)
- Unknown algorithm handling
- Error handling / job history
- Manual trigger (trigger_job)
- Lifecycle (start / shutdown)

All Neo4j calls mocked via AsyncMock — no container required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from engine.config.schema import (
    DomainSpec,
    GDSJobScheduleSpec,
    GDSJobSpec,
    GDSProjectionSpec,
)
from engine.gds.scheduler import GDSScheduler

# ── Helpers ───────────────────────────────────────────────


def _job(
    name: str,
    algorithm: str,
    schedule_type: str = "cron",
    cron: str | None = "0 2 * * *",
    node_labels: list[str] | None = None,
    edge_types: list[str] | None = None,
    writeproperty: str | None = None,
    sourceedge: str | None = None,
    writeedge: str | None = None,
) -> GDSJobSpec:
    return GDSJobSpec(
        name=name,
        algorithm=algorithm,
        schedule=GDSJobScheduleSpec(type=schedule_type, cron=cron if schedule_type == "cron" else None),
        projection=GDSProjectionSpec(
            nodelabels=node_labels or ["Facility"],
            edgetypes=edge_types or ["TRANSACTED_WITH"],
        ),
        writeproperty=writeproperty,
        sourceedge=sourceedge,
        writeedge=writeedge,
    )


def _minimal_spec(jobs: list[GDSJobSpec]) -> DomainSpec:
    raw = {
        "domain": {"id": "test-domain", "name": "Test", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                },
            ],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        "queryschema": {"matchdirections": ["d1"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
        "gdsjobs": [j.model_dump() for j in jobs],
    }
    return DomainSpec(**raw)


def _mock_driver(return_data: list | None = None) -> AsyncMock:
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=return_data or [])
    return driver


# ── Job Registration ──────────────────────────────────────


class TestRegistration:
    def test_register_cron_jobs(self):
        jobs = [_job("louvain_nightly", "louvain")]
        spec = _minimal_spec(jobs)
        driver = _mock_driver()
        scheduler = GDSScheduler(spec, driver)

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            scheduler.register_jobs()
            mock_add.assert_called_once()
            call_kwargs = mock_add.call_args
            assert call_kwargs.kwargs["id"] == "louvain_nightly"

    def test_register_manual_job_no_add(self):
        jobs = [_job("manual_job", "louvain", schedule_type="manual")]
        spec = _minimal_spec(jobs)
        driver = _mock_driver()
        scheduler = GDSScheduler(spec, driver)

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            scheduler.register_jobs()
            mock_add.assert_not_called()

    def test_cron_missing_expression_raises(self):
        job = _job("bad", "louvain", schedule_type="cron", cron=None)
        # Override to force None cron
        job.schedule = GDSJobScheduleSpec(type="cron", cron=None)
        spec = _minimal_spec([job])
        driver = _mock_driver()
        scheduler = GDSScheduler(spec, driver)
        with pytest.raises(ValueError, match="cron expression required"):
            scheduler._register_cron_job(job)


# ── Algorithm Dispatch ────────────────────────────────────


class TestAlgorithmDispatch:
    @pytest.mark.asyncio
    async def test_louvain_executes_project_and_write(self):
        driver = _mock_driver([{"communityCount": 5, "modularity": 0.42}])
        job = _job("test_louvain", "louvain")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)

        assert result["status"] == "success"
        assert driver.execute_query.call_count >= 2  # project + louvain + drop
        assert "duration_sec" in result

    @pytest.mark.asyncio
    async def test_cooccurrence_requires_sourceedge_and_writeedge(self):
        driver = _mock_driver()
        job = _job("test_cooc", "cooccurrence", sourceedge=None, writeedge=None)
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "failed"
        assert "sourceedge" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_cooccurrence_happy_path(self):
        driver = _mock_driver([{"edges_created": 15}])
        job = _job("test_cooc", "cooccurrence", sourceedge="ACCEPTS_POLYMER", writeedge="CO_PROCESSES")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_reinforcement_creates_accepted_and_rejected(self):
        driver = _mock_driver([{"accepted_edges": 10}])
        # Override return for second call
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"accepted_edges": 10}],  # accepted
                [{"rejected_edges": 3}],  # rejected
                [],  # prune accepted
                [],  # prune rejected
            ]
        )
        job = _job("test_reinf", "reinforcement")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "success"
        assert result["accepted_edges"] == 10
        assert result["rejected_edges"] == 3

    @pytest.mark.asyncio
    async def test_temporal_recency_creates_and_prunes(self):
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"edges_created": 20}],
                [{"edges_pruned": 5}],
            ]
        )
        job = _job("test_temporal", "temporalrecency")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "success"
        assert result["edges_created"] == 20
        assert result["edges_pruned"] == 5

    @pytest.mark.asyncio
    async def test_geoproximity_creates_colocated_edges(self):
        driver = _mock_driver([{"edges_created": 8}])
        job = _job("test_geo", "geoproximity")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_equipment_sync_materializes_edges(self):
        driver = _mock_driver([{"edges_created": 24}])
        job = _job("test_equip", "equipmentsync")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_unknown_algorithm_skipped(self):
        driver = _mock_driver()
        job = _job("test_unknown", "nonexistent_algo")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "skipped"
        assert "unknown algorithm" in result["reason"]


# ── Error Handling ────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_execute_job_catches_exception(self):
        driver = _mock_driver()
        driver.execute_query = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        job = _job("test_fail", "louvain")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.execute_job(job)
        assert result["status"] == "failed"
        assert "Neo4j down" in result["error"]

    @pytest.mark.asyncio
    async def test_job_history_records_failures(self):
        driver = _mock_driver()
        driver.execute_query = AsyncMock(side_effect=RuntimeError("boom"))
        job = _job("history_test", "louvain")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        await scheduler.execute_job(job)
        assert len(scheduler.job_history) == 1
        assert scheduler.job_history[0]["status"] == "failed"
        assert scheduler.job_history[0]["job"] == "history_test"

    @pytest.mark.asyncio
    async def test_job_history_records_successes(self):
        driver = _mock_driver([{"edges_created": 1}])
        job = _job("ok_job", "equipmentsync")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        await scheduler.execute_job(job)
        assert len(scheduler.job_history) == 1
        assert scheduler.job_history[0]["status"] == "success"


# ── Manual Trigger ────────────────────────────────────────


class TestManualTrigger:
    @pytest.mark.asyncio
    async def test_trigger_existing_job(self):
        driver = _mock_driver([{"edges_created": 5}])
        job = _job("my_job", "equipmentsync", schedule_type="manual")
        spec = _minimal_spec([job])
        scheduler = GDSScheduler(spec, driver)

        result = await scheduler.trigger_job("my_job")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_trigger_unknown_job_raises(self):
        spec = _minimal_spec([])
        driver = _mock_driver()
        scheduler = GDSScheduler(spec, driver)

        with pytest.raises(ValueError, match="not found"):
            await scheduler.trigger_job("ghost")


# ── Lifecycle ─────────────────────────────────────────────


class TestLifecycle:
    def test_start_and_shutdown(self):
        spec = _minimal_spec([])
        driver = _mock_driver()
        scheduler = GDSScheduler(spec, driver)

        with (
            patch.object(scheduler.scheduler, "start") as mock_start,
            patch.object(scheduler.scheduler, "shutdown") as mock_stop,
        ):
            scheduler.start()
            mock_start.assert_called_once()
            scheduler.shutdown()
            mock_stop.assert_called_once()
