"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [startup, wiring, gap-fixes]
owner: engine-team
status: active
--- /L9_META ---

engine/startup_wiring.py — Gap-fix activation for GraphLifecycle.startup()

Called ONCE from engine/boot.py::_apply_gap_fixes() during application startup,
before the engine serves any requests.

All imports resolve to modules that exist in engine/.
FIX(RULE-2): top-level `graph/` package references have been removed.
              Gap-6 now imports from engine.gds.community_export, which is
              the canonical location per the fixed file structure (§1 of build
              protocol). The orphan `graph/` package is no longer referenced.
"""

from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def apply_all_gap_fixes(
    pg_dsn: str,
    neo4j_driver: object,
    domain_pack_loader: object,
) -> None:
    """Activate all merged-but-not-wired gap fixes.

    Must be called once during application startup, before serving requests.
    Fail-closed: any exception propagates to GraphLifecycle.startup() and
    prevents the engine from coming up with partially-wired infrastructure.

    Args:
        pg_dsn: asyncpg-compatible DSN string (required, non-empty).
        neo4j_driver: GraphDriver instance (already connected).
        domain_pack_loader: DomainPackLoader instance (already configured).
    """
    if not pg_dsn:
        msg = "apply_all_gap_fixes: pg_dsn is empty — cannot wire audit pool"
        raise ValueError(msg)

    # ── Gap-5: Wire PostgreSQL audit pool ────────────────────────────────────
    # FIX(RULE-9 + GAP-5): audit pool MUST exist before compliance flush runs.
    # Without this, every ce.flush_audit() call silently no-ops or warns.
    from engine.compliance.audit_persistence import configure_audit_pool

    pg_pool = await asyncpg.create_pool(pg_dsn, min_size=2, max_size=10)
    await configure_audit_pool(pg_pool)
    logger.info("startup: Gap-5 audit pool wired (min=2, max=10)")

    # ── Gap-3: Load domain KB rules into inference registry ──────────────────
    # FIX(RULE-9 + GAP-3): rules must load before the first handle_match call
    # attempts to run gate compilation against the rule registry.
    from engine.inference_rule_registry import load_domain_rules

    domains_loaded = 0
    for domain_id in domain_pack_loader.list_domains():
        spec = domain_pack_loader.load_domain(domain_id)
        if spec and spec.kb:
            load_domain_rules(spec.kb)
            domains_loaded += 1
    logger.info("startup: Gap-3 inference rules loaded for %d domain(s)", domains_loaded)

    # ── Gap-2: Initialise GRAPH→ENRICH return channel ────────────────────────
    # FIX(RULE-9 + GAP-2): singleton must exist before any convergence pass
    # attempts GraphToEnrichReturnChannel.get_instance() — explicit init here
    # eliminates the race condition between boot and first packet arrival.
    from engine.graph_return_channel import GraphToEnrichReturnChannel

    GraphToEnrichReturnChannel.get_instance()
    logger.info("startup: Gap-2 return channel initialised (singleton ready)")

    # ── Gap-6: Register community-export hook on GDSScheduler ────────────────
    # FIX(RULE-2 + RULE-9 + GAP-6): import path corrected from orphan `graph/`
    # package to canonical `engine.gds.community_export`. GDSScheduler is
    # imported from `engine.gds.scheduler` (the only registered scheduler).
    from engine.gds.community_export import export_community_labels_to_enrich
    from engine.gds.scheduler import GDSScheduler

    GDSScheduler.register_post_job_hook(
        job_type="louvain",
        hook=lambda tenant_id, domain_id: export_community_labels_to_enrich(
            neo4j_driver, tenant_id, domain_id
        ),
    )
    logger.info("startup: Gap-6 community export hook registered on GDSScheduler")

    # ── Gap-9: v1 bridge blocked by file replacement (no action needed here) ──
    # engine/inference_bridge.py raises ImportError at module load.
    # Any stale caller crashes at import time, not at startup — no registration
    # step required. Verified importable in _assert_convergence_patch_importable.
    logger.info("startup: Gap-9 v1 bridge guard is passive — no action required")

    logger.info("startup: all gap fixes applied successfully")
