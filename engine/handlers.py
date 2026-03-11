"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [chassis-bridge, handlers]
owner: engine-team
status: active
--- /L9_META ---

Action handlers for L9 chassis integration.
Handlers receive (tenant: str, payload: dict) and return dict.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from engine.compliance.engine import ComplianceEngine
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec
from engine.gates.compiler import GateCompiler
from engine.gds.scheduler import GDSScheduler
from engine.graph.driver import GraphDriver
from engine.scoring.assembler import ScoringAssembler
from engine.sync.generator import SyncGenerator
from engine.traversal.assembler import TraversalAssembler
from engine.traversal.resolver import ParameterResolver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

_graph_driver: GraphDriver | None = None
_domain_loader: DomainPackLoader | None = None
_gds_schedulers: dict[str, GDSScheduler] = {}


class EngineError(Exception):
    """Base engine error with structured context."""

    def __init__(self, message: str, *, action: str, tenant: str, detail: str | None = None) -> None:
        self.action = action
        self.tenant = tenant
        self.detail = detail
        super().__init__(message)


class ValidationError(EngineError):
    """Payload validation failure."""


class ExecutionError(EngineError):
    """Neo4j or runtime execution failure."""


def init_dependencies(graph_driver: GraphDriver, domain_loader: DomainPackLoader) -> None:
    """Called by chassis at startup to inject dependencies."""
    global _graph_driver, _domain_loader
    _graph_driver = graph_driver
    _domain_loader = domain_loader


def _require_deps() -> tuple[GraphDriver, DomainPackLoader]:
    if _graph_driver is None or _domain_loader is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _graph_driver, _domain_loader


def _require_key(payload: dict[str, Any], key: str, action: str, tenant: str) -> Any:
    """Extract required key with structured error."""
    if key not in payload:
        raise ValidationError(
            f"Missing required field '{key}' in {action} payload",
            action=action,
            tenant=tenant,
        )
    return payload[key]


# Allowed Cypher function patterns for enrich action (whitelist approach)
_SAFE_CYPHER_FUNCTIONS = frozenset(
    [
        "coalesce(",
        "toInteger(",
        "toFloat(",
        "toString(",
        "size(",
        "length(",
        "trim(",
        "toLower(",
        "toUpper(",
        "abs(",
        "round(",
        "ceil(",
        "floor(",
        "sqrt(",
        "log(",
        "exp(",
        "datetime(",
        "date(",
        "time(",
        "duration(",
        "point(",
        "distance(",
    ]
)

# Dangerous Cypher keywords that must be blocked
_DANGEROUS_PATTERNS = frozenset(
    [
        "call",
        "create",
        "merge",
        "delete",
        "remove",
        "set",
        "match",
        "return",
        "with",
        "unwind",
        "foreach",
        "load",
        "using",
        "detach",
        "optional",
        "union",
        "apoc",
        "gds",
        "dbms",
        "db.",
        "//",
        "/*",
        "$$",
        "${",
    ]
)

# Valid property name pattern (alphanumeric + underscore, must start with letter/underscore)
_PROPERTY_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Direct property access: n.<identifier> preceded by start-of-string or an operator/whitespace.
# Intentionally does NOT match n.<identifier> preceded by '(' to block substring(n.prop,...) bypass.
_DIRECT_PROPERTY_RE = re.compile(r"(?:^|[\s+\-*/])n\.[a-zA-Z_][a-zA-Z0-9_]*")


def _check_dangerous_patterns(expr_stripped: str, expr_lower: str) -> None:
    """Raise ValidationError if expression contains any dangerous pattern."""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in ("//", "/*", "$$", "${", "db."):
            if pattern in expr_lower:
                raise ValidationError(
                    f"Forbidden pattern '{pattern}' in expression",
                    action="enrich",
                    tenant="unknown",
                )
        else:
            keyword_re = re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
            if keyword_re.search(expr_stripped):
                raise ValidationError(
                    f"Forbidden keyword '{pattern}' in expression",
                    action="enrich",
                    tenant="unknown",
                )


def _try_safe_literal(expr_stripped: str, expr_lower: str) -> str | None:
    """
    Return expr_stripped if it is a safe literal (bool, null, number, quoted string).
    Return None if it is not a simple literal.
    Raise ValidationError if it looks like a quoted string but contains injections.
    """
    if expr_lower in ("true", "false", "null"):
        return expr_stripped
    try:
        float(expr_stripped)
        return expr_stripped
    except ValueError:
        pass
    # Single or double quoted string literal
    for quote in ("'", '"'):
        if expr_stripped.startswith(quote) and expr_stripped.endswith(quote) and expr_stripped.count(quote) == 2:
            inner = expr_stripped[1:-1]
            if "'" in inner or '"' in inner or "\\" in inner:
                raise ValidationError(
                    "String literals cannot contain quotes or escapes",
                    action="enrich",
                    tenant="unknown",
                )
            return expr_stripped
    return None


def _validate_property_refs_and_chars(expr_stripped: str) -> None:
    """Validate property names and allowed characters in the expression."""
    property_refs = re.findall(r"n\.([a-zA-Z_][a-zA-Z0-9_]*)", expr_stripped)
    for prop in property_refs:
        if not _PROPERTY_NAME_RE.match(prop):
            raise ValidationError(
                f"Invalid property name '{prop}' in expression",
                action="enrich",
                tenant="unknown",
            )
    allowed_operators = {"+", "-", "*", "/", "%", "(", ")", ",", ".", " "}
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    allowed_chars.update(allowed_operators)
    for char in expr_stripped:
        if char not in allowed_chars:
            raise ValidationError(
                f"Disallowed character '{char}' in expression",
                action="enrich",
                tenant="unknown",
            )


def _sanitize_expression(expr: str) -> str:
    """
    Sanitize Cypher expression for enrich action.
    Uses strict whitelist approach: only allow known-safe patterns.
    Raises ValidationError if expression contains potentially dangerous patterns.
    """
    expr_stripped = expr.strip()
    expr_lower = expr_stripped.lower()

    # Fast-path: safe literals bypass the dangerous-pattern check entirely.
    safe_literal = _try_safe_literal(expr_stripped, expr_lower)
    if safe_literal is not None:
        return safe_literal

    _check_dangerous_patterns(expr_stripped, expr_lower)

    has_safe_function = any(
        expr_lower.startswith(f) or f" {f}" in expr_lower or f"({f}" in expr_lower for f in _SAFE_CYPHER_FUNCTIONS
    )
    # Only allow direct property references (n.<identifier>), not function calls that wrap
    # property access (e.g. substring(n.name, 0, 3) is rejected here).
    has_property_access = bool(_DIRECT_PROPERTY_RE.search(expr_stripped))

    if not has_safe_function and not has_property_access:
        raise ValidationError(
            f"Expression '{expr_stripped}' does not match allowed patterns",
            action="enrich",
            tenant="unknown",
        )

    _validate_property_refs_and_chars(expr_stripped)
    return expr_stripped


async def handle_match(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Gate-then-score graph traversal."""
    graph_driver, domain_loader = _require_deps()
    start_time = time.monotonic()

    query = _require_key(payload, "query", "match", tenant)
    match_direction = _require_key(payload, "match_direction", "match", tenant)

    raw_top_n = payload.get("top_n", 10)
    try:
        top_n = max(1, min(int(raw_top_n), 1000))
    except (TypeError, ValueError):
        top_n = 10

    weights = payload.get("weights", {})
    domain_spec = domain_loader.load_domain(tenant)

    compliance = ComplianceEngine(domain_spec)
    if compliance.enabled:
        compliance.validate_gates(domain_spec.gates)
        query = compliance.check_match_request(
            tenant=tenant,
            query=query,
            match_direction=match_direction,
        )

    resolver = ParameterResolver(domain_spec)
    resolved_query = resolver.resolve_parameters(query)

    gate_compiler = GateCompiler(domain_spec)
    where_clause = gate_compiler.compile_all_gates(match_direction)

    traversal_assembler = TraversalAssembler(domain_spec)
    traversal_clauses = traversal_assembler.assemble_traversal(match_direction)

    scoring_assembler = ScoringAssembler(domain_spec)
    scoring_clause = scoring_assembler.assemble_scoring_clause(match_direction, weights)

    candidate_labels = [c.label for c in domain_spec.matchentities.candidate if c.matchdirection == match_direction]
    if not candidate_labels:
        raise ValidationError(
            f"No candidate entity for direction {match_direction!r}",
            action="match",
            tenant=tenant,
        )
    candidate_label = sanitize_label(candidate_labels[0])

    cypher = (
        f"MATCH (candidate:{candidate_label})\n"
        + "\n".join(traversal_clauses)
        + "\n"
        + f"WHERE {where_clause}\n"
        + f"{scoring_clause}\n"
        + "RETURN candidate, score\n"
        + "ORDER BY score DESC\n"
        + "LIMIT $top_n"
    )

    try:
        results = await graph_driver.execute_query(
            cypher=cypher,
            parameters={"query": resolved_query, "top_n": top_n},
            database=domain_spec.domain.id,
        )
    except Exception as exc:
        logger.error("Match query failed for tenant=%s", tenant, exc_info=True)
        raise ExecutionError(
            "Match query execution failed",
            action="match",
            tenant=tenant,
            detail="Query execution error",
        ) from exc

    execution_time_ms = (time.monotonic() - start_time) * 1000
    response = {
        "candidates": results,
        "query_id": f"q_{uuid.uuid4().hex[:12]}",
        "match_direction": match_direction,
        "total_candidates": len(results),
        "execution_time_ms": round(execution_time_ms, 2),
    }

    if compliance.enabled:
        response = compliance.redact_response(response, tenant)
    return response


async def handle_sync(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Batch UNWIND MERGE/MATCH SET for graph entities."""
    graph_driver, domain_loader = _require_deps()

    entity_type = _require_key(payload, "entity_type", "sync", tenant)
    batch = _require_key(payload, "batch", "sync", tenant)

    if not isinstance(batch, list) or len(batch) == 0:
        raise ValidationError(
            "Sync batch must be a non-empty list",
            action="sync",
            tenant=tenant,
        )

    domain_spec = domain_loader.load_domain(tenant)
    if not domain_spec.sync:
        raise ValidationError("No sync endpoints configured", action="sync", tenant=tenant)

    endpoint_spec = next(
        (e for e in domain_spec.sync.endpoints if e.path.rstrip("/").rsplit("/", 1)[-1] == entity_type),
        None,
    )
    if not endpoint_spec:
        raise ValidationError(
            f"No sync endpoint for entity type {entity_type!r}",
            action="sync",
            tenant=tenant,
        )

    # Run compliance checks on sync request
    compliance = ComplianceEngine(domain_spec)
    if compliance.enabled:
        compliance.check_sync_request(
            tenant=tenant,
            entity_type=entity_type,
            batch=batch,
            endpoint_spec=endpoint_spec,
        )

    generator = SyncGenerator(domain_spec)
    cypher = generator.generate_sync_query(endpoint_spec, batch)

    try:
        await graph_driver.execute_query(
            cypher=cypher,
            parameters={"batch": batch, "tenant": tenant},
            database=domain_spec.domain.id,
        )
    except Exception as exc:
        raise ExecutionError(
            "Sync query execution failed",
            action="sync",
            tenant=tenant,
            detail=str(exc),
        ) from exc

    return {"status": "success", "entity_type": entity_type, "synced_count": len(batch)}


async def handle_admin(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Admin: introspection, schema init, GDS trigger."""
    graph_driver, domain_loader = _require_deps()
    subaction = _require_key(payload, "subaction", "admin", tenant)

    if subaction == "list_domains":
        return {"domains": domain_loader.list_domains()}

    if subaction == "get_domain":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        return {"domain": spec.model_dump(mode="json")}

    if subaction == "init_schema":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        count = await _init_schema(graph_driver, spec)
        return {"status": "schema_initialized", "constraints_created": count}

    if subaction == "trigger_gds":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        job_name = _require_key(payload, "job_name", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        scheduler = _get_or_create_scheduler(spec, graph_driver)
        result = await scheduler.trigger_job(job_name)
        return {"status": "triggered", "job": job_name, "result": result}

    raise ValidationError(f"Unknown admin subaction: {subaction!r}", action="admin", tenant=tenant)


async def _init_schema(driver: GraphDriver, spec: DomainSpec) -> int:
    """Create Neo4j constraints and indexes from ontology."""
    db = spec.domain.id
    count = 0
    for node in spec.ontology.nodes:
        label = sanitize_label(node.label)
        for prop in node.properties:
            if prop.required:
                cypher = (
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{sanitize_label(prop.name)} IS NOT NULL"
                )
                try:
                    await driver.execute_query(cypher, database=db)
                    count += 1
                except Exception as exc:
                    logger.warning("Constraint failed for %s.%s: %s", label, prop.name, exc)
        id_props = [p for p in node.properties if p.required and "id" in p.name.lower()]
        for prop in id_props:
            cypher = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{sanitize_label(prop.name)} IS UNIQUE"
            try:
                await driver.execute_query(cypher, database=db)
                count += 1
            except Exception as exc:
                logger.warning("Uniqueness constraint failed %s.%s: %s", label, prop.name, exc)
    return count


def _get_or_create_scheduler(spec: DomainSpec, driver: GraphDriver) -> GDSScheduler:
    domain_id = spec.domain.id
    if domain_id not in _gds_schedulers:
        scheduler = GDSScheduler(spec, driver)
        scheduler.register_jobs()
        _gds_schedulers[domain_id] = scheduler
    return _gds_schedulers[domain_id]


async def handle_outcomes(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Write TransactionOutcome nodes and RESULTED_IN edges."""
    graph_driver, domain_loader = _require_deps()

    match_id = _require_key(payload, "match_id", "outcomes", tenant)
    candidate_id = _require_key(payload, "candidate_id", "outcomes", tenant)
    outcome = _require_key(payload, "outcome", "outcomes", tenant)

    if outcome not in ("success", "failure", "partial"):
        raise ValidationError(
            f"Invalid outcome: {outcome!r}. Must be success|failure|partial.",
            action="outcomes",
            tenant=tenant,
        )

    domain_spec = domain_loader.load_domain(tenant)
    outcome_id = f"out_{uuid.uuid4().hex[:12]}"

    cypher = """
    CREATE (o:TransactionOutcome {
        outcome_id: $outcome_id, match_id: $match_id,
        candidate_id: $candidate_id, outcome: $outcome,
        value: $value, created_at: datetime(), tenant: $tenant
    })
    WITH o
    OPTIONAL MATCH (c {entity_id: $candidate_id})
    FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
        CREATE (c)-[:RESULTED_IN]->(o)
    )
    RETURN o.outcome_id AS outcome_id
    """
    try:
        await graph_driver.execute_query(
            cypher=cypher,
            parameters={
                "outcome_id": outcome_id,
                "match_id": match_id,
                "candidate_id": candidate_id,
                "outcome": outcome,
                "value": payload.get("value"),
                "tenant": tenant,
            },
            database=domain_spec.domain.id,
        )
    except Exception as exc:
        raise ExecutionError(
            "Outcome write failed",
            action="outcomes",
            tenant=tenant,
            detail=str(exc),
        ) from exc

    compliance = ComplianceEngine(domain_spec)
    if compliance.enabled:
        compliance.log_outcome(tenant=tenant, outcome_id=outcome_id, outcome=outcome)
    return {"status": "recorded", "outcome_id": outcome_id}


async def handle_resolve(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Entity resolution: create RESOLVED_FROM edge between duplicate entities."""
    graph_driver, domain_loader = _require_deps()

    entity_type = _require_key(payload, "entity_type", "resolve", tenant)
    source_id = _require_key(payload, "source_id", "resolve", tenant)
    target_id = _require_key(payload, "target_id", "resolve", tenant)
    confidence = payload.get("confidence", 1.0)
    signal = payload.get("signal", "manual")

    domain_spec = domain_loader.load_domain(tenant)
    label = sanitize_label(entity_type)
    resolution_id = f"res_{uuid.uuid4().hex[:12]}"

    cypher = f"""
    MATCH (source:{label} {{entity_id: $source_id}})
    MATCH (target:{label} {{entity_id: $target_id}})
    CREATE (source)-[r:RESOLVED_FROM {{
        resolution_id: $resolution_id, confidence: $confidence,
        signal: $signal, created_at: datetime(), tenant: $tenant
    }}]->(target)
    RETURN r.resolution_id AS resolution_id
    """
    try:
        await graph_driver.execute_query(
            cypher=cypher,
            parameters={
                "source_id": source_id,
                "target_id": target_id,
                "resolution_id": resolution_id,
                "confidence": confidence,
                "signal": signal,
                "tenant": tenant,
            },
            database=domain_spec.domain.id,
        )
    except Exception as exc:
        raise ExecutionError(
            "Entity resolution failed",
            action="resolve",
            tenant=tenant,
            detail=str(exc),
        ) from exc

    return {
        "status": "resolved",
        "resolution_id": resolution_id,
        "source_id": source_id,
        "target_id": target_id,
    }


async def handle_health(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Health check: Neo4j connectivity and domain spec validity."""
    graph_driver, domain_loader = _require_deps()
    checks: dict[str, str] = {"neo4j": "unknown", "domain_spec": "unknown"}

    try:
        await graph_driver.execute_query("RETURN 1 AS ping", database="system")
        checks["neo4j"] = "ok"
    except Exception:
        checks["neo4j"] = "error: connection_failed"

    try:
        domain_loader.load_domain(tenant)
        checks["domain_spec"] = "ok"
    except Exception:
        checks["domain_spec"] = "error: config_invalid"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


async def handle_healthcheck(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Alias for handle_health (spec compatibility)."""
    return await handle_health(tenant, payload)


async def handle_enrich(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich action: add computed properties to graph entities.

    Payload schema:
      - entity_type: str       # Node label to enrich
      - entity_ids: list[str]  # Optional: specific entities (all if omitted)
      - enrichments: list[dict] # Each: {property: str, expression: str}

    Returns:
      - enriched_count: int
      - entity_type: str
      - tenant: str
    """
    graph_driver, domain_loader = _require_deps()
    domain_spec = domain_loader.load_domain(tenant)

    entity_type = payload.get("entity_type")
    if not entity_type:
        raise ValidationError("entity_type required", action="enrich", tenant=tenant)

    entity_ids = payload.get("entity_ids", [])
    enrichments = payload.get("enrichments", [])

    if not enrichments:
        return {"enriched_count": 0, "entity_type": entity_type, "tenant": tenant}

    label = sanitize_label(entity_type)

    set_clauses = []
    for enrich in enrichments:
        prop = enrich.get("property", "")
        expr = enrich.get("expression", "")
        if prop and expr:
            safe_prop = sanitize_label(prop)
            safe_expr = _sanitize_expression(expr)
            set_clauses.append(f"n.{safe_prop} = {safe_expr}")

    if not set_clauses:
        return {"enriched_count": 0, "entity_type": entity_type, "tenant": tenant}

    if entity_ids:
        cypher = f"""
        MATCH (n:{label})
        WHERE n.entity_id IN $entity_ids
        SET {", ".join(set_clauses)}
        RETURN count(n) AS enriched_count
        """
        params = {"entity_ids": entity_ids}
    else:
        cypher = f"""
        MATCH (n:{label})
        SET {", ".join(set_clauses)}
        RETURN count(n) AS enriched_count
        """
        params = {}

    result = await graph_driver.execute_query(
        cypher=cypher,
        parameters=params,
        database=domain_spec.domain.id,
    )

    count = result[0]["enriched_count"] if result else 0
    return {"enriched_count": count, "entity_type": entity_type, "tenant": tenant}


def register_all(chassis_router: Any) -> None:
    """Register all 8 action handlers with the chassis."""
    chassis_router.register_handler("match", handle_match)
    chassis_router.register_handler("sync", handle_sync)
    chassis_router.register_handler("admin", handle_admin)
    chassis_router.register_handler("outcomes", handle_outcomes)
    chassis_router.register_handler("resolve", handle_resolve)
    chassis_router.register_handler("health", handle_health)
    chassis_router.register_handler("healthcheck", handle_healthcheck)
    chassis_router.register_handler("enrich", handle_enrich)
    logger.info("Registered 8 action handlers: match, sync, admin, outcomes, resolve, health, healthcheck, enrich")
