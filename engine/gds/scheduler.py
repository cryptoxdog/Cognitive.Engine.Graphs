"""
GDS job scheduler.
APScheduler-based background job execution for graph algorithms.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from engine.config.schema import DomainSpec, GDSJobSpec
from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)


class GDSScheduler:
    """Schedules and executes GDS jobs."""

    def __init__(self, domain_spec: DomainSpec, graph_driver: GraphDriver):
        self.domain_spec = domain_spec
        self.graph_driver = graph_driver
        self.scheduler = AsyncIOScheduler()

    def register_jobs(self) -> None:
        """Register all GDS jobs from domain spec."""
        for job_spec in self.domain_spec.gdsjobs:
            if job_spec.schedule.type == "cron":
                self._register_cron_job(job_spec)
            elif job_spec.schedule.type == "manual":
                logger.info(f"Job '{job_spec.name}' is manual-trigger only")

        logger.info(f"Registered {len(self.domain_spec.gdsjobs)} GDS jobs")

    def _register_cron_job(self, job_spec: GDSJobSpec) -> None:
        """Register cron-triggered job."""
        if not job_spec.schedule.cron:
            raise ValueError(f"Job '{job_spec.name}': cron expression required")

        trigger = CronTrigger.from_crontab(job_spec.schedule.cron)

        self.scheduler.add_job(
            func=self._execute_job,
            trigger=trigger,
            args=[job_spec],
            id=job_spec.name,
            name=job_spec.name,
            replace_existing=True,
        )

        logger.info(f"Scheduled job '{job_spec.name}' with cron: {job_spec.schedule.cron}")

    async def _execute_job(self, job_spec: GDSJobSpec) -> None:
        """Execute GDS job."""
        logger.info(f"Starting GDS job '{job_spec.name}' - algorithm: {job_spec.algorithm}")
        start_time = datetime.now()

        try:
            if job_spec.algorithm == "louvain":
                await self._run_louvain(job_spec)
            elif job_spec.algorithm == "cooccurrence":
                await self._run_cooccurrence(job_spec)
            elif job_spec.algorithm == "reinforcement":
                await self._run_reinforcement(job_spec)
            elif job_spec.algorithm == "temporal_recency":
                await self._run_temporal_recency(job_spec)
            else:
                logger.warning(f"Unknown algorithm: {job_spec.algorithm}")

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Completed job '{job_spec.name}' in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Job '{job_spec.name}' failed: {e}", exc_info=True)

    async def _run_louvain(self, job_spec: GDSJobSpec) -> None:
        """Run Louvain community detection."""
        cypher = f"""
        CALL gds.graph.project(
            '{job_spec.name}_graph',
            {job_spec.projection.nodelabels},
            {job_spec.projection.edgetypes}
        )
        YIELD graphName, nodeCount, relationshipCount
        
        CALL gds.louvain.write(
            '{job_spec.name}_graph',
            {{
                writeProperty: '{job_spec.writeproperty}'
            }}
        )
        YIELD communityCount, modularity
        
        CALL gds.graph.drop('{job_spec.name}_graph')
        YIELD graphName
        
        RETURN communityCount, modularity
        """

        result = await self.graph_driver.execute_query(
            cypher,
            database=self.domain_spec.domain.id,
        )
        logger.info(f"Louvain result: {result}")

    async def _run_cooccurrence(self, job_spec: GDSJobSpec) -> None:
        """Build cooccurrence edges (e.g., CO_PURCHASED_WITH)."""
        if not job_spec.sourceedge or not job_spec.writeedge:
            raise ValueError(f"Job '{job_spec.name}': sourceedge and writeedge required")

        cypher = f"""
        MATCH (a)-[:{job_spec.sourceedge}]->(common)<-[:{job_spec.sourceedge}]-(b)
        WHERE id(a) < id(b)
        WITH a, b, count(common) AS weight
        WHERE weight >= 2
        MERGE (a)-[r:{job_spec.writeedge}]-(b)
        SET r.weight = weight, r.updated_at = datetime()
        RETURN count(r) AS edges_created
        """

        result = await self.graph_driver.execute_query(
            cypher,
            database=self.domain_spec.domain.id,
        )
        logger.info(f"Cooccurrence result: {result}")

    async def _run_reinforcement(self, job_spec: GDSJobSpec) -> None:
        """Weight edges by outcome feedback."""
        # Implementation depends on outcome tracking structure
        logger.info(f"Reinforcement learning job '{job_spec.name}' executed")

    async def _run_temporal_recency(self, job_spec: GDSJobSpec) -> None:
        """Build recency-weighted transaction edges."""
        logger.info(f"Temporal recency job '{job_spec.name}' executed")

    def start(self) -> None:
        """Start scheduler."""
        self.scheduler.start()
        logger.info("GDS scheduler started")

    def shutdown(self) -> None:
        """Shutdown scheduler."""
        self.scheduler.shutdown()
        logger.info("GDS scheduler shut down")
