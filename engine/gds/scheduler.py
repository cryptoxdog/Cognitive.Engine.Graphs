"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [gds, scheduler, louvain]
owner: engine-team
status: active
--- /L9_META ---

engine/gds/scheduler.py
APScheduler-based background job execution for graph algorithms.
Manages Louvain community detection, co-occurrence, reinforcement
learning edge weights, and temporal recency pruning.

All algorithms execute real Cypher against Neo4j — no stubs.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from engine.config.schema import DomainSpec, GDSJobSpec
from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)


class GDSScheduler:
    """
    Schedules and executes GDS jobs defined in domain spec YAML.

    Supported algorithms:
        - louvain: Community detection via GDS Louvain
        - cooccurrence: Bipartite projection → co-occurrence edges
        - reinforcement: Outcome-weighted edge scoring (ACCEPTED/REJECTED)
        - temporalrecency: Recency-decay edge creation + pruning
        - geoproximity: Haversine distance-based COLOCATED_WITH edges
        - equipmentsync: Boolean prop → HASEQUIPMENT edge materialization
    """

    def __init__(self, domain_spec: DomainSpec, graph_driver: GraphDriver):
        self.domain_spec = domain_spec
        self.graph_driver = graph_driver
        self.scheduler = AsyncIOScheduler()
        self._job_history: List[Dict] = []

    def register_jobs(self) -> None:
        """Register all GDS jobs from domain spec."""
        for job_spec in self.domain_spec.gdsjobs:
            if job_spec.schedule.type == "cron":
                self._register_cron_job(job_spec)
            elif job_spec.schedule.type == "manual":
                logger.info(f"Job {job_spec.name} is manual-trigger only")
        logger.info(f"Registered {len(self.domain_spec.gdsjobs)} GDS jobs")

    def _register_cron_job(self, job_spec: GDSJobSpec) -> None:
        if not job_spec.schedule.cron:
            raise ValueError(f"Job {job_spec.name}: cron expression required")
        trigger = CronTrigger.from_crontab(job_spec.schedule.cron)
        self.scheduler.add_job(
            func=self.execute_job,
            trigger=trigger,
            args=[job_spec],
            id=job_spec.name,
            name=job_spec.name,
            replace_existing=True,
        )
        logger.info(f"Scheduled job {job_spec.name} with cron {job_spec.schedule.cron}")

    async def execute_job(self, job_spec: GDSJobSpec) -> Dict:
        """Execute GDS job and record result."""
        logger.info(f"Starting GDS job {job_spec.name} — algorithm={job_spec.algorithm}")
        start = datetime.now()
        result = {}

        try:
            algo = job_spec.algorithm
            if algo == "louvain":
                result = await self._run_louvain(job_spec)
            elif algo == "cooccurrence":
                result = await self._run_cooccurrence(job_spec)
            elif algo == "reinforcement":
                result = await self._run_reinforcement(job_spec)
            elif algo == "temporalrecency":
                result = await self._run_temporal_recency(job_spec)
            elif algo == "geoproximity":
                result = await self._run_geoproximity(job_spec)
            elif algo == "equipmentsync":
                result = await self._run_equipment_sync(job_spec)
            else:
                logger.warning(f"Unknown algorithm: {algo}")
                result = {"status": "skipped", "reason": f"unknown algorithm: {algo}"}

            duration = (datetime.now() - start).total_seconds()
            logger.info(f"Completed job {job_spec.name} in {duration:.2f}s")
            result["duration_sec"] = duration
            result["status"] = result.get("status", "success")

        except Exception as e:
            logger.error(f"Job {job_spec.name} failed: {e}", exc_info=True)
            result = {"status": "failed", "error": str(e)}

        self._job_history.append({
            "job": job_spec.name,
            "algorithm": job_spec.algorithm,
            "timestamp": datetime.now().isoformat(),
            **result,
        })
        return result

    # ── Algorithm Implementations ──────────────────────────────

    async def _run_louvain(self, job_spec: GDSJobSpec) -> Dict:
        """Run Louvain community detection via GDS."""
        db = self.domain_spec.domain.id
        graph_name = f"{job_spec.name}_graph"

        # Pre-cleanup: drop stale projection if it exists (fixes crash on re-run)
        pre_drop = f"""
        CALL gds.graph.exists('{graph_name}') YIELD exists
        WITH exists WHERE exists
        CALL gds.graph.drop('{graph_name}') YIELD graphName
        RETURN graphName
        """
        try:
            await self.graph_driver.execute_query(pre_drop, database=db)
        except Exception:
            pass  # Graph didn't exist; expected on first run

        # Use json.dumps for proper Cypher array syntax
        node_labels = json.dumps(job_spec.projection.nodelabels)
        edge_types = json.dumps(job_spec.projection.edgetypes)
        write_prop = job_spec.writeproperty or "communityId"

        project_cypher = f"""
        CALL gds.graph.project('{graph_name}', {node_labels}, {edge_types})
        YIELD graphName, nodeCount, relationshipCount
        RETURN graphName, nodeCount, relationshipCount
        """
        try:
            await self.graph_driver.execute_query(project_cypher, database=db)

            louvain_cypher = f"""
            CALL gds.louvain.write('{graph_name}', {{writeProperty: '{write_prop}'}})
            YIELD communityCount, modularity
            RETURN communityCount, modularity
            """
            result = await self.graph_driver.execute_query(louvain_cypher, database=db)
            data = result[0] if result else {}
            logger.info(f"Louvain: {data}")
            return {"communities": data.get("communityCount"), "modularity": data.get("modularity")}
        finally:
            drop_cypher = f"CALL gds.graph.drop('{graph_name}') YIELD graphName RETURN graphName"
            try:
                await self.graph_driver.execute_query(drop_cypher, database=db)
            except Exception as drop_err:
                logger.error(f"Failed to drop projected graph '{graph_name}': {drop_err}")

    async def _run_cooccurrence(self, job_spec: GDSJobSpec) -> Dict:
        """Build co-occurrence edges from bipartite projection."""
        if not job_spec.sourceedge or not job_spec.writeedge:
            raise ValueError(f"Job {job_spec.name}: sourceedge and writeedge required")
        cypher = f"""
        MATCH (a)-[:{job_spec.sourceedge}]->(common)<-[:{job_spec.sourceedge}]-(b)
        WHERE id(a) < id(b)
        WITH a, b, count(common) AS weight
        WHERE weight >= 2
        MERGE (a)-[r:{job_spec.writeedge}]->(b)
        SET r.weight = weight, r.updated_at = datetime()
        RETURN count(r) AS edges_created
        """
        result = await self.graph_driver.execute_query(
            cypher, database=self.domain_spec.domain.id
        )
        edges = result[0]["edges_created"] if result else 0
        logger.info(f"Co-occurrence: {edges} edges created/updated")
        return {"edges_created": edges}

    async def _run_reinforcement(self, job_spec: GDSJobSpec) -> Dict:
        """
        Weight edges by transaction outcome feedback.

        Aggregates transaction outcomes into:
        - ACCEPTED_MATERIAL_FROM edges (positive reinforcement)
        - REJECTED_MATERIAL_FROM edges (negative signal)

        Each edge gets:
        - count: total accepted/rejected shipments
        - success_rate: accepted / total
        - recency_score: exp(-age_days / 180.0) on most recent event
        - last_event_date: timestamp of most recent outcome

        Decay: exp(-age_days / half_life_days) per spec v1.1
        Half-life: 180 days for acceptance, 90 days for rejection (shorter = faster decay)
        """
        db = self.domain_spec.domain.id

        # Phase 1: Build ACCEPTED_MATERIAL_FROM edges
        accepted_cypher = """
        MATCH (buyer:Facility)-[t:TRANSACTED_WITH]->(seller:Facility)
        WHERE t.outcome IS NOT NULL
        WITH buyer, seller,
             sum(CASE WHEN t.outcome = 'success' THEN 1 ELSE 0 END) AS accepted,
             sum(CASE WHEN t.outcome = 'failure' THEN 1 ELSE 0 END) AS rejected,
             max(CASE WHEN t.outcome = 'success' THEN t.created_at ELSE null END) AS last_accept,
             sum(CASE WHEN t.outcome = 'success' THEN coalesce(t.value_usd, 0) ELSE 0 END) AS total_value,
             avg(CASE WHEN t.outcome = 'success' THEN t.quality_grade ELSE null END) AS avg_quality
        WHERE accepted > 0
        MERGE (buyer)-[r:ACCEPTED_MATERIAL_FROM]->(seller)
        SET r.count = accepted,
            r.success_rate = toFloat(accepted) / (accepted + rejected),
            r.last_event_date = last_accept,
            r.recency_score = CASE
                WHEN last_accept IS NOT NULL
                THEN exp(-1.0 * duration.inDays(last_accept, datetime()).days / 180.0)
                ELSE 0.0
            END,
            r.aggregate_value_usd = total_value,
            r.avg_quality_grade = avg_quality
        RETURN count(r) AS accepted_edges
        """

        # Phase 2: Build REJECTED_MATERIAL_FROM edges
        rejected_cypher = """
        MATCH (buyer:Facility)-[t:TRANSACTED_WITH]->(seller:Facility)
        WHERE t.outcome = 'failure'
        WITH buyer, seller,
             count(t) AS rejected,
             max(t.created_at) AS last_reject,
             head(collect(t.reason_code)) AS primary_reason
        MERGE (buyer)-[r:REJECTED_MATERIAL_FROM]->(seller)
        SET r.count = rejected,
            r.last_rejection_date = last_reject,
            r.primary_reason_code = primary_reason,
            r.recency_score = CASE
                WHEN last_reject IS NOT NULL
                THEN exp(-1.0 * duration.inDays(last_reject, datetime()).days / 90.0)
                ELSE 0.0
            END
        RETURN count(r) AS rejected_edges
        """

        # Phase 3: Prune stale reinforcement edges (recency < 0.1) - split into separate queries
        prune_accepted_cypher = """
        MATCH ()-[r:ACCEPTED_MATERIAL_FROM]-()
        WHERE r.recency_score < 0.1
        DELETE r
        RETURN count(r) AS pruned
        """
        prune_rejected_cypher = """
        MATCH ()-[r:REJECTED_MATERIAL_FROM]-()
        WHERE r.recency_score < 0.1
        DELETE r
        RETURN count(r) AS pruned
        """

        accepted_result = await self.graph_driver.execute_query(accepted_cypher, database=db)
        rejected_result = await self.graph_driver.execute_query(rejected_cypher, database=db)

        try:
            await self.graph_driver.execute_query(prune_accepted_cypher, database=db)
            await self.graph_driver.execute_query(prune_rejected_cypher, database=db)
        except Exception as e:
            logger.warning(f"Prune step skipped: {e}")

        accepted_count = accepted_result[0]["accepted_edges"] if accepted_result else 0
        rejected_count = rejected_result[0]["rejected_edges"] if rejected_result else 0

        logger.info(
            f"Reinforcement: {accepted_count} accepted edges, "
            f"{rejected_count} rejected edges"
        )
        return {
            "accepted_edges": accepted_count,
            "rejected_edges": rejected_count,
        }

    async def _run_temporal_recency(self, job_spec: GDSJobSpec) -> Dict:
        """
        Create/update RECENTLY_TRANSACTED_WITH edges with recency decay.

        Formula: recency_score = exp(-age_days / 90.0)
        Prune threshold: recency_score < 0.1 (≈207 days old)
        Half-life: 62 days

        Per spec v0.4.0: TRANSACTED_WITH is permanent historical record.
        RECENTLY_TRANSACTED_WITH is the hot temporal overlay.
        """
        db = self.domain_spec.domain.id

        # Create/update recency edges
        create_cypher = """
        MATCH (buyer:Facility)-[t:TRANSACTED_WITH]->(seller:Facility)
        WHERE t.last_date IS NOT NULL
        WITH buyer, seller, t,
             duration.inDays(t.last_date, datetime()).days AS age_days
        WHERE age_days <= 207
        MERGE (buyer)-[r:RECENTLY_TRANSACTED_WITH]->(seller)
        SET r.last_txn_date = t.last_date,
            r.txn_count_90d = CASE WHEN age_days <= 90
                THEN coalesce(t.count_90d, 1) ELSE 0 END,
            r.recency_score = exp(-1.0 * age_days / 90.0),
            r.total_volume_lbs_90d = coalesce(t.volume_90d, 0)
        RETURN count(r) AS edges_created
        """

        # Prune stale edges
        prune_cypher = """
        MATCH ()-[r:RECENTLY_TRANSACTED_WITH]-()
        WHERE r.recency_score < 0.1
        DELETE r
        RETURN count(r) AS edges_pruned
        """

        create_result = await self.graph_driver.execute_query(create_cypher, database=db)
        prune_result = await self.graph_driver.execute_query(prune_cypher, database=db)

        created = create_result[0]["edges_created"] if create_result else 0
        pruned = prune_result[0]["edges_pruned"] if prune_result else 0

        logger.info(f"Temporal recency: {created} edges created, {pruned} pruned")
        return {"edges_created": created, "edges_pruned": pruned}

    async def _run_geoproximity(self, job_spec: GDSJobSpec) -> Dict:
        """Build COLOCATED_WITH edges based on haversine distance."""
        db = self.domain_spec.domain.id
        max_km = 500
        decay_km = 200

        # Use directional MERGE to avoid duplicate edges
        cypher = f"""
        MATCH (a:Facility), (b:Facility)
        WHERE a.facility_id < b.facility_id
          AND a.lat IS NOT NULL AND b.lat IS NOT NULL
        WITH a, b,
             point.distance(
                 point({{latitude: a.lat, longitude: a.lon}}),
                 point({{latitude: b.lat, longitude: b.lon}})
             ) / 1000.0 AS dist_km
        WHERE dist_km <= {max_km}
        MERGE (a)-[r:COLOCATED_WITH]->(b)
        SET r.distance_km = dist_km,
            r.proximity_score = 1.0 / (1.0 + dist_km / {decay_km})
        RETURN count(r) AS edges_created
        """
        result = await self.graph_driver.execute_query(cypher, database=db)
        edges = result[0]["edges_created"] if result else 0
        logger.info(f"Geo-proximity: {edges} COLOCATED_WITH edges")
        return {"edges_created": edges}

    async def _run_equipment_sync(self, job_spec: GDSJobSpec) -> Dict:
        """Materialize boolean Facility props as HAS_EQUIPMENT edges."""
        db = self.domain_spec.domain.id
        cypher = """
        MATCH (f:Facility)
        WITH f, [
            CASE WHEN f.has_shredder = true THEN 'shredder' END,
            CASE WHEN f.has_granulator = true THEN 'granulator' END,
            CASE WHEN f.has_wash_line = true THEN 'washline' END,
            CASE WHEN f.has_extruder = true THEN 'extruder' END,
            CASE WHEN f.has_sorting_line = true THEN 'sortingline' END,
            CASE WHEN f.handles_regrind = true THEN 'regrindhandler' END,
            CASE WHEN f.handles_flake = true THEN 'flakehandler' END,
            CASE WHEN f.handles_rollstock = true THEN 'rollstockhandler' END
        ] AS equipment_names
        UNWIND equipment_names AS eq_name
        WITH f, eq_name WHERE eq_name IS NOT NULL
        MATCH (e:EquipmentType {name: eq_name})
        MERGE (f)-[:HAS_EQUIPMENT]->(e)
        RETURN count(*) AS edges_created
        """
        result = await self.graph_driver.execute_query(cypher, database=db)
        edges = result[0]["edges_created"] if result else 0
        logger.info(f"Equipment sync: {edges} HAS_EQUIPMENT edges")
        return {"edges_created": edges}

    # ── Lifecycle ──────────────────────────────────────────

    async def trigger_job(self, job_name: str) -> Dict:
        """Manually trigger a registered job by name."""
        for job_spec in self.domain_spec.gdsjobs:
            if job_spec.name == job_name:
                return await self.execute_job(job_spec)
        raise ValueError(f"Job '{job_name}' not found in domain spec")

    def start(self) -> None:
        self.scheduler.start()
        logger.info("GDS scheduler started")

    def shutdown(self) -> None:
        self.scheduler.shutdown()
        logger.info("GDS scheduler shut down")

    @property
    def job_history(self) -> List[Dict]:
        return list(self._job_history)
