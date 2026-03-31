"""
GAP-FIX STARTUP WIRING
Add these calls to your application lifespan / startup handler in order.
This file is a recipe — adapt paths to match your actual app entrypoint.
"""
from __future__ import annotations
import asyncpg
import logging

logger = logging.getLogger(__name__)


async def apply_all_gap_fixes(pg_dsn: str, neo4j_driver, domain_pack_loader) -> None:
    """
    Call once during application startup, before serving requests.
    Parameters:
        pg_dsn            – asyncpg-compatible DSN string
        neo4j_driver      – AsyncDriver from neo4j-driver
        domain_pack_loader – DomainPackLoader instance
    """

    # ── Gap 5: Wire PostgreSQL audit pool ────────────────────────────────────
    from shared.audit_persistence import configure_audit_pool
    pg_pool = await asyncpg.create_pool(pg_dsn, min_size=2, max_size=10)
    await configure_audit_pool(pg_pool)
    logger.info("startup: Gap-5 audit pool wired")

    # ── Gap 3: Load domain KB rules into inference registry ──────────────────
    from engine.inference_rule_registry import load_domain_rules
    for domain_id in domain_pack_loader.list_domains():
        spec = domain_pack_loader.load_domain(domain_id)
        if spec and spec.kb:
            load_domain_rules(spec.kb)
    logger.info("startup: Gap-3 inference rules loaded")

    # ── Gap 2: Initialise GRAPH→ENRICH return channel ────────────────────────
    from engine.graph_return_channel import GraphToEnrichReturnChannel
    GraphToEnrichReturnChannel.get_instance()
    logger.info("startup: Gap-2 return channel initialised")

    # ── Gap 6: Register community-export hook on GDS scheduler ───────────────
    from graph.community_export import export_community_labels_to_enrich
    try:
        from graph.gds_scheduler import GDSScheduler
        GDSScheduler.register_post_job_hook(
            job_type="louvain",
            hook=lambda tenant_id, domain_id: export_community_labels_to_enrich(
                neo4j_driver, tenant_id, domain_id
            ),
        )
        logger.info("startup: Gap-6 community export hook registered")
    except ImportError:
        logger.warning("startup: GDSScheduler not found — register Gap-6 hook manually")

    # ── Gap 9: v1 bridge blocked by file replacement (no action needed here) ──
    # engine/inference_bridge.py has been replaced with inference_bridge_v1_guard.py
    # Any stray import will raise ImportError at import time, not at startup.

    logger.info("startup: all gap fixes applied successfully")
