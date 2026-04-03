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

from engine.auth.capabilities import (
    ACTION_PERMISSION_MAP,
    Capability,
    CapabilitySet,
    check_action_permission,
    get_capability_validator,
)
from engine.compliance.engine import ComplianceEngine
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec
from engine.gates.compiler import GateCompiler
from engine.gds.scheduler import GDSScheduler
from engine.graph.driver import GraphDriver
from engine.scoring.assembler import ScoringAssembler
from engine.state import get_state
from engine.sync.generator import SyncGenerator
from engine.traversal.assembler import TraversalAssembler
from engine.traversal.resolver import ParameterResolutionError, ParameterResolver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


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
    """Called by chassis/boot at startup to inject dependencies into EngineState.

    W4-01: Populates the EngineState singleton rather than module-level globals.
    """
    state = get_state()
    state._graph_driver = graph_driver
    state._domain_loader = domain_loader
    import os

    allowlist_raw = os.getenv("TENANT_ALLOWLIST", "")
    if allowlist_raw.strip():
        state._tenant_allowlist = {t.strip() for t in allowlist_raw.split(",") if t.strip()}
        logger.info("Tenant allowlist configured: %s", state._tenant_allowlist)
    else:
        state._tenant_allowlist = None
        logger.warning("No TENANT_ALLOWLIST configured — all tenants accessible")
    state._initialized = True


def _validate_tenant_access(tenant: str, action: str, *, allowed_tenants: list[str] | None = None) -> None:
    """Reject requests for unauthorized tenants.

    Checks both the legacy TENANT_ALLOWLIST env var and, when W3-01 is active,
    the JWT ``allowed_tenants`` claim forwarded from the auth middleware.
    """
    state = get_state()
    allowlist = state.tenant_allowlist
    if allowlist is not None and tenant not in allowlist:
        raise ValidationError(
            f"Tenant '{tenant}' not in authorized allowlist",
            action=action,
            tenant=tenant,
        )

    # W3-01: JWT-based tenant authorization
    from engine.config.settings import settings as _w3_settings

    if _w3_settings.tenant_auth_enabled and allowed_tenants is not None:
        if tenant not in allowed_tenants and "*" not in allowed_tenants:
            raise ValidationError(
                f"Tenant '{tenant}' not in JWT allowed_tenants",
                action=action,
                tenant=tenant,
            )


def _require_deps() -> tuple[GraphDriver, DomainPackLoader]:
    state = get_state()
    if not state.is_initialized:
        msg = "Dependencies not initialized. Call init_dependencies() first."
        raise RuntimeError(msg)
    return state.graph_driver, state.domain_loader


def _get_compliance_engine(domain_spec: DomainSpec) -> ComplianceEngine:
    """W4-04: Get-or-create ComplianceEngine from the singleton pool.

    Stores one ComplianceEngine per domain_id in EngineState.compliance_engines.
    Avoids per-request instantiation overhead.
    """
    state = get_state()
    domain_id = domain_spec.domain.id
    if domain_id not in state.compliance_engines:
        state.compliance_engines[domain_id] = ComplianceEngine(domain_spec)
    return state.compliance_engines[domain_id]


def _build_capability_set(domain_spec: DomainSpec) -> CapabilitySet | None:
    """Build a CapabilitySet from domain spec capabilities (W3-02).

    Returns None if no capabilities are defined in the spec.
    """
    if not domain_spec.capabilities:
        return None
    caps = [{"actions": c.actions, "allowed_subjects": c.allowed_subjects} for c in domain_spec.capabilities]
    return CapabilitySet(caps)


def _enforce_capability(tenant: str, action: str, domain_spec: DomainSpec) -> None:
    """W3-02/W3-03: Check capability-based access control.

    Only enforced when CAPABILITY_AUTH_ENABLED is True and the domain spec
    declares capabilities. Raises ValidationError on denial.
    """
    from engine.config.settings import settings as _cap_settings

    if not _cap_settings.capability_auth_enabled:
        return

    cap_set = _build_capability_set(domain_spec)
    if cap_set is None:
        return

    if not check_action_permission(tenant, action, cap_set):
        required = ACTION_PERMISSION_MAP.get(action, action)
        raise ValidationError(
            f"Tenant '{tenant}' lacks capability '{required}' for action '{action}'",
            action=action,
            tenant=tenant,
        )


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
_DANGEROUS_PATTERNS = (
    "detach",  # must be before "delete" — DETACH DELETE reports detach
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
)

# Valid property name pattern (alphanumeric + underscore, must start with letter/underscore)
_PROPERTY_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Direct property access: n.<identifier> preceded by start-of-string or an operator/whitespace.
# Intentionally does NOT match n.<identifier> preceded by '(' to block substring(n.prop,...) bypass.
# Also matches Cypher parameter references ($param_name).
_DIRECT_PROPERTY_RE = re.compile(r"(?:^|[\s+\-*/])n\.[a-zA-Z_][a-zA-Z0-9_]*|\$[a-zA-Z_][a-zA-Z0-9_]*")


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
        float(expr_stripped)  # nosemgrep: float-requires-try-except
    except ValueError:
        pass
    else:
        return expr_stripped
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
    allowed_operators = {"+", "-", "*", "/", "%", "(", ")", ",", ".", " ", "$"}
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
        expr_lower.startswith(f.lower()) or f" {f.lower()}" in expr_lower or f"({f.lower()}" in expr_lower
        for f in _SAFE_CYPHER_FUNCTIONS
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


_WEIGHT_FLOOR = 0.0
_WEIGHT_CEILING = 1.0
_WEIGHT_SUM_TOLERANCE = 1e-9


def _validate_match_weights(weights: dict[str, float], tenant: str) -> None:
    """W1-02: Validate user-supplied scoring weights.

    Each weight must be in [0, 1] and the total sum must be <= 1.0.
    """
    for key, val in weights.items():
        try:
            w = float(val)
        except (TypeError, ValueError) as exc:
            msg = f"Weight '{key}' is not a valid number"
            raise ValidationError(msg, action="match", tenant=tenant) from exc
        if w < _WEIGHT_FLOOR or w > _WEIGHT_CEILING:
            msg = f"Weight '{key}' = {w} is outside allowed range [{_WEIGHT_FLOOR}, {_WEIGHT_CEILING}]"
            raise ValidationError(msg, action="match", tenant=tenant)

    weight_sum = sum(float(v) for v in weights.values())
    if weight_sum > _WEIGHT_CEILING + _WEIGHT_SUM_TOLERANCE:
        msg = f"Weights sum to {weight_sum:.4f}, exceeding {_WEIGHT_CEILING}"
        raise ValidationError(msg, action="match", tenant=tenant)


async def handle_match(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Gate-then-score graph traversal."""
    graph_driver, domain_loader = _require_deps()
    _validate_tenant_access(tenant, "match")
    start_time = time.monotonic()

    query = _require_key(payload, "query", "match", tenant)
    match_direction = _require_key(payload, "match_direction", "match", tenant)

    raw_top_n = payload.get("top_n", 10)
    try:
        top_n = max(1, min(int(raw_top_n), 1000))
    except (TypeError, ValueError):
        top_n = 10

    weights = payload.get("weights", {})

    # W1-02: Validate user-supplied weights are in [0, 1] and sum to <= 1.0
    if weights:
        from engine.config.settings import settings

        if settings.score_clamp_enabled:
            _validate_match_weights(weights, tenant)

    domain_spec = domain_loader.load_domain(tenant)
    _enforce_capability(tenant, "match", domain_spec)

    compliance = _get_compliance_engine(domain_spec)
    if compliance.enabled:
        compliance.validate_gates(domain_spec.gates)
        query = compliance.check_match_request(
            tenant=tenant,
            query=query,
            match_direction=match_direction,
        )

    resolver = ParameterResolver(domain_spec)
    try:
        resolved_query = resolver.resolve_parameters(query)
    except ParameterResolutionError as exc:
        raise ValidationError(
            str(exc),
            action="match",
            tenant=tenant,
            detail="Derived parameter resolution failed (W1-05 strict mode)",
        ) from exc

    for field in domain_spec.queryschema.fields:
        if field.name not in resolved_query:
            resolved_query[field.name] = field.default

    gate_compiler = GateCompiler(domain_spec)
    where_clause = gate_compiler.compile_all_gates(match_direction)

    traversal_assembler = TraversalAssembler(domain_spec)
    traversal_clauses = traversal_assembler.assemble_traversal(match_direction)

    scoring_assembler = ScoringAssembler(domain_spec, graph_driver=graph_driver)
    # Convergence loop: load learned weights from feedback loop
    if domain_spec.feedbackloop.enabled and domain_spec.feedbackloop.signal_weights.enabled:
        await scoring_assembler.load_learned_weights()
    scoring_clause, pareto_metadata = scoring_assembler.assemble_scoring_clause(match_direction, weights)

    candidate_labels = [c.label for c in domain_spec.matchentities.candidate if c.matchdirection == match_direction]
    if not candidate_labels:
        raise ValidationError(
            f"No candidate entity for direction {match_direction!r}",
            action="match",
            tenant=tenant,
        )
    cypher = (
        f"MATCH (candidate:{sanitize_label(candidate_labels[0])})\n"
        + "\n".join(traversal_clauses)
        + "\n"
        + f"WHERE {where_clause}\n"
        + f"{scoring_clause}\n"
        + "RETURN candidate, score\n"
        + "ORDER BY score DESC\n"
        + "LIMIT $top_n"
    )

    try:
        parameters = {**resolved_query, "top_n": top_n}
        results = await graph_driver.execute_query(
            cypher=cypher,
            parameters=parameters,
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

    # Build Pareto candidates from results and compute front metadata
    pareto_candidates_input: list[Any] | None = None
    if results:
        from engine.config.settings import settings as _settings

        if _settings.pareto_enabled:
            from engine.scoring.pareto import ParetoCandidate

            pareto_candidates_input = [
                ParetoCandidate(
                    candidate_id=str(r.get("candidate", {}).get("entity_id", i)),
                    dimension_scores={
                        k: float(v)
                        for k, v in r.items()
                        if k not in ("candidate", "score") and isinstance(v, (int, float))
                    },
                )
                for i, r in enumerate(results)
            ]
            # Re-run assembler with Pareto candidates to get front metadata
            _, pareto_metadata = scoring_assembler.assemble_scoring_clause(
                match_direction, weights, pareto_candidates=pareto_candidates_input
            )

        # --- Milestone 2.1: Spec-driven constraint enforcement ---
        if domain_spec.decision_arbitration.enabled:
            from engine.scoring.pareto_integrator import (
                apply_constraint_penalties,
                apply_pareto_filter,
            )

            constraint_dicts = [
                {
                    "dimension": c.dimension,
                    "threshold": c.threshold,
                    "hard": c.hard,
                    "penalty": c.penalty,
                }
                for c in domain_spec.decision_arbitration.constraints
            ]

            if constraint_dicts:
                results = apply_constraint_penalties(list(results), constraint_dicts)

            # Spec-driven Pareto filter using declared objectives
            arb_dims = [obj.dimension for obj in domain_spec.decision_arbitration.pareto_config.objectives]
            if arb_dims and len(results) > 1:
                arb_pareto = apply_pareto_filter(results, arb_dims)
                if pareto_metadata is None:
                    pareto_metadata = {}
                pareto_metadata["arbitration"] = {
                    "frontsize": arb_pareto["frontsize"],
                    "pruned_pct": arb_pareto["pruned_pct"],
                    "nondominated_ids": arb_pareto["nondominated"],
                }

    execution_time_ms = (time.monotonic() - start_time) * 1000

    # --- W2-04: Score Normalization ---
    from engine.config.settings import settings as _w2_settings

    candidates_out = list(results)
    scoring_meta: dict[str, Any] = {
        "weights_used": weights,
        "normalization_applied": False,
    }

    if candidates_out:
        raw_scores = [c.get("score", 0.0) if isinstance(c, dict) else 0.0 for c in candidates_out]
        scoring_meta["raw_max"] = max(raw_scores) if raw_scores else 0.0
        scoring_meta["raw_min"] = min(raw_scores) if raw_scores else 0.0

        if _w2_settings.score_normalize and len(candidates_out) > 0:
            raw_max = scoring_meta["raw_max"]
            raw_min = scoring_meta["raw_min"]
            score_range = raw_max - raw_min
            if score_range > 0:
                for c in candidates_out:
                    if isinstance(c, dict) and "score" in c:
                        c["score"] = round((c["score"] - raw_min) / score_range, 6)
            elif len(candidates_out) == 1 and isinstance(candidates_out[0], dict):
                candidates_out[0]["score"] = 1.0
            scoring_meta["normalization_applied"] = True
    else:
        scoring_meta["raw_max"] = 0.0
        scoring_meta["raw_min"] = 0.0

    # --- W2-03: Confidence Checking ---
    if _w2_settings.confidence_check_enabled:
        # Attach per-dimension scores to candidates and run monoculture check
        dim_names = scoring_assembler.last_active_dimension_names
        for c in candidates_out:
            if isinstance(c, dict) and not c.get("dimension_scores"):
                dim_scores: dict[str, float] = {}
                for dn in dim_names:
                    if dn in c:
                        dim_scores[dn] = c[dn]
                if dim_scores:
                    c["dimension_scores"] = dim_scores

        from engine.scoring.confidence import ConfidenceChecker

        checker = ConfidenceChecker(
            monoculture_threshold=_w2_settings.monoculture_threshold,
            ensemble_max_divergence=_w2_settings.ensemble_max_divergence,
        )
        candidates_out = checker.annotate_candidates(candidates_out)

    # BFS causal explanations when causal subgraph is enabled
    if domain_spec.causal.enabled and candidates_out:
        from engine.causal.serializer import CausalSubgraphSerializer

        serializer = CausalSubgraphSerializer(graph_driver, domain_spec)
        candidate_label = candidate_labels[0]
        for c in candidates_out:
            if isinstance(c, dict):
                cand = c.get("candidate", {})
                entity_id = str(cand.get("entity_id", "")) if isinstance(cand, dict) else ""
                if entity_id:
                    explanation = await serializer.serialize_neighborhood(
                        node_id=entity_id,
                        node_label=candidate_label,
                        max_depth=min(domain_spec.causal.chain_depth_limit, 2),
                    )
                    c["match_explanation"] = explanation

    response = {
        "candidates": candidates_out,
        "query_id": f"q_{uuid.uuid4().hex[:12]}",
        "match_direction": match_direction,
        "total_candidates": len(candidates_out),
        "execution_time_ms": round(execution_time_ms, 2),
        "scoring_meta": scoring_meta,
    }
    if pareto_metadata:
        response["pareto"] = pareto_metadata

    # Flush audit entries (currently logs warning since db_pool=None;
    # will persist to PostgreSQL once provisioned)
    await compliance.flush_audit()

    if compliance.enabled:
        response = compliance.redact_response(response, tenant)
    return response


async def handle_sync(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Batch UNWIND MERGE/MATCH SET for graph entities."""
    graph_driver, domain_loader = _require_deps()
    _validate_tenant_access(tenant, "sync")

    entity_type = _require_key(payload, "entity_type", "sync", tenant)
    batch = _require_key(payload, "batch", "sync", tenant)

    if not isinstance(batch, list) or len(batch) == 0:
        raise ValidationError(
            "Sync batch must be a non-empty list",
            action="sync",
            tenant=tenant,
        )

    # --- W2-02: Outcome record type via sync ---
    from engine.config.settings import settings as _sync_settings

    if entity_type == "outcome" and _sync_settings.feedback_enabled:
        domain_spec = domain_loader.load_domain(tenant)
        _enforce_capability(tenant, "sync", domain_spec)
        synced = 0
        for item in batch:
            if not isinstance(item, dict):
                continue
            match_id = item.get("match_id")
            candidate_id = item.get("chosen_candidate_id")
            outcome_val = item.get("outcome")
            if outcome_val not in ("positive", "negative", "neutral"):
                continue
            outcome_id = f"out_{uuid.uuid4().hex[:12]}"
            cypher = """
            CREATE (o:Outcome {
                outcome_id: $outcome_id, match_id: $match_id,
                candidate_id: $candidate_id, outcome: $outcome,
                created_at: datetime(), tenant: $tenant
            })
            WITH o
            OPTIONAL MATCH (c {entity_id: $candidate_id})
            FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
                CREATE (c)-[:HAS_OUTCOME]->(o)
            )
            """
            try:
                await graph_driver.execute_query(
                    cypher=cypher,
                    parameters={
                        "outcome_id": outcome_id,
                        "match_id": match_id,
                        "candidate_id": candidate_id,
                        "outcome": outcome_val,
                        "tenant": tenant,
                    },
                    database=domain_spec.domain.id,
                )
                synced += 1
            except Exception:
                logger.warning("Failed to sync outcome for match_id=%s", match_id, exc_info=True)
        return {"status": "success", "entity_type": "outcome", "synced_count": synced}

    domain_spec = domain_loader.load_domain(tenant)
    _enforce_capability(tenant, "sync", domain_spec)
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
    compliance = _get_compliance_engine(domain_spec)
    if compliance.enabled:
        compliance.check_sync_request(
            tenant=tenant,
            entity_type=entity_type,
            batch=batch,
            endpoint_spec=endpoint_spec,
        )

    # R3: Causal edge validation when domain has causal edges enabled
    rejected_count = 0
    if domain_spec.causal.enabled and payload.get("edge_type"):
        from engine.causal.causal_validator import CausalEdgeRuntimeValidator

        validator = CausalEdgeRuntimeValidator(domain_spec.causal)
        batch, rejected = validator.validate_batch(batch, payload["edge_type"])
        rejected_count = len(rejected)
        if not batch:
            return {
                "status": "all_rejected",
                "entity_type": entity_type,
                "synced_count": 0,
                "rejected_count": rejected_count,
            }

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

    await compliance.flush_audit()
    result: dict[str, Any] = {
        "status": "success",
        "entity_type": entity_type,
        "synced_count": len(batch),
    }
    if rejected_count > 0:
        result["rejected_count"] = rejected_count
    return result


async def handle_admin(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Admin: introspection, schema init, GDS trigger, capability delegation."""
    graph_driver, domain_loader = _require_deps()
    _validate_tenant_access(tenant, "admin")
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

    # --- W2-01: Score Calibration ---
    if subaction == "calibration_run":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        from engine.scoring.calibration import ScoreCalibrator

        calibrator = ScoreCalibrator(spec)
        report = calibrator.generate_calibration_report(domain_id)
        return {"status": "calibration_report", **report}

    # --- W2-02: Score Feedback ---
    if subaction == "score_feedback":
        from engine.config.settings import settings as _fb_settings

        if not _fb_settings.feedback_enabled:
            return {"status": "disabled", "message": "Feedback loop is disabled. Set FEEDBACK_ENABLED=True."}
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        # Read recent outcomes from Neo4j
        outcome_cypher = """
        MATCH (o:TransactionOutcome)
        WHERE o.tenant = $tenant
        RETURN o.outcome AS outcome, o.candidate_id AS candidate_id,
               o.match_id AS match_id, o.value AS value
        ORDER BY o.created_at DESC
        LIMIT 500
        """
        try:
            outcome_records = await graph_driver.execute_query(
                cypher=outcome_cypher,
                parameters={"tenant": tenant},
                database=spec.domain.id,
            )
        except Exception as exc:
            raise ExecutionError(
                "Failed to read outcomes for feedback",
                action="admin",
                tenant=tenant,
                detail=str(exc),
            ) from exc

        from engine.scoring.feedback import OutcomeFeedback

        feedback = OutcomeFeedback(outcome_records)
        result = feedback.compute_feedback()
        return {"status": "feedback_computed", **result}

    if subaction == "apply_weight_proposal":
        from engine.config.settings import settings as _fb_settings

        if not _fb_settings.feedback_enabled:
            return {"status": "disabled", "message": "Feedback loop is disabled. Set FEEDBACK_ENABLED=True."}
        proposed = _require_key(payload, "proposed_weights", "admin", tenant)
        current = _require_key(payload, "current_weights", "admin", tenant)
        from engine.scoring.feedback import OutcomeFeedback

        new_weights = OutcomeFeedback.apply_weights(current, proposed)
        return {"status": "weights_applied", "new_weights": new_weights}

    # ── W3-04: Capability Delegation ────────────────────────────
    if subaction == "delegate_capability":
        source_tenant = _require_key(payload, "source_tenant", "admin", tenant)
        target_tenant = _require_key(payload, "target_tenant", "admin", tenant)
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        actions = _require_key(payload, "actions", "admin", tenant)
        expires_in = payload.get("expires_in_seconds", 0.0)

        validator = get_capability_validator()

        # Find or create a root capability for the source tenant
        parent_cap = None
        for cap in validator._registry.values():
            if cap.tenant_id == source_tenant and cap.is_active():
                if all(a in cap.allowed_actions for a in actions):
                    parent_cap = cap
                    break

        if parent_cap is None:
            # Create root capability for source tenant
            parent_cap = Capability(
                tenant_id=source_tenant,
                domain_id="*",
                allowed_actions=frozenset(actions),
            )
            validator.register(parent_cap)

        child_cap = validator.derive_capability(
            parent_cap,
            scope_restriction={
                "domain_id": domain_id,
                "allowed_actions": actions,
            },
            expires_in_seconds=expires_in,
        )
        # Override tenant on child to target
        object.__setattr__(child_cap, "tenant_id", target_tenant)
        child_cap.proof_hash = child_cap._compute_proof_hash()

        # Audit the delegation
        domain_spec_for_audit = domain_loader.load_domain(domain_id) if domain_id != "*" else None
        compliance_engine = ComplianceEngine(domain_spec_for_audit) if domain_spec_for_audit else None
        if compliance_engine:
            compliance_engine.log_admin(tenant=tenant, subaction="delegate_capability")
        logger.info(
            "Capability delegated: %s → %s (domain=%s, actions=%s, cap_id=%s)",
            source_tenant,
            target_tenant,
            domain_id,
            actions,
            child_cap.capability_id,
        )
        return {
            "status": "delegated",
            "capability": child_cap.to_dict(),
            "delegation": {
                "source_tenant": source_tenant,
                "target_tenant": target_tenant,
                "domain_id": domain_id,
                "actions": actions,
            },
        }

    if subaction == "revoke_capability":
        capability_id = _require_key(payload, "capability_id", "admin", tenant)
        validator = get_capability_validator()
        revoked = validator.revoke_capability(capability_id)
        if not revoked:
            raise ValidationError(
                f"Capability '{capability_id}' not found in registry",
                action="admin",
                tenant=tenant,
            )

        # Audit the revocation
        logger.info("Capability revoked: %s (by tenant=%s)", capability_id, tenant)
        return {
            "status": "revoked",
            "capability_id": capability_id,
            "audit": validator.audit_summary(),
        }

    if subaction == "capability_audit":
        validator = get_capability_validator()
        return {
            "status": "audit",
            "summary": validator.audit_summary(),
        }

    # --- W6-01: KGE Activation Pathway ---
    if subaction == "trigger_kge":
        from chassis.errors import FeatureNotEnabled
        from engine.config.settings import settings as _kge_s

        if not _kge_s.kge_enabled:
            raise FeatureNotEnabled("KGE", flag="KGE_ENABLED", action="admin", tenant=tenant)
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        if spec.kge is None:
            raise ValidationError(
                "Domain spec has no 'kge' section — cannot activate KGE",
                action="admin",
                tenant=tenant,
            )
        # Validate embedding dimension consistency (W1-01 cross-ref)
        if spec.kge.embeddingdim != _kge_s.kge_embedding_dim:
            raise ValidationError(
                f"Domain spec kge.embeddingdim={spec.kge.embeddingdim} differs from "
                f"settings.kge_embedding_dim={_kge_s.kge_embedding_dim}",
                action="admin",
                tenant=tenant,
            )
        from engine.kge.compound_e3d import CompoundE3D, CompoundE3DConfig

        config = CompoundE3DConfig.from_kge_spec(spec.kge)
        kge_model = CompoundE3D(config)  # noqa: F841 — instantiation validates config
        # Smoke test: verify vector index exists by running a simple query
        smoke_ok = True
        smoke_detail = "vector index reachable"
        try:
            index_name = spec.kge.vectorindex.name if spec.kge.vectorindex else f"{domain_id}_kge_index"
            await graph_driver.execute_query(
                "SHOW INDEXES YIELD name WHERE name = $idx RETURN name",
                parameters={"idx": index_name},
                database=domain_id,
            )
        except Exception as exc:
            smoke_ok = False
            smoke_detail = f"vector index check failed: {exc}"
            logger.warning("KGE smoke test failed for domain=%s: %s", domain_id, exc)
        return {
            "status": "kge_activated" if smoke_ok else "kge_activated_with_warnings",
            "domain_id": domain_id,
            "embedding_dim": config.embedding_dim,
            "training_relations": config.training_relations,
            "model": spec.kge.model,
            "smoke_test": {"ok": smoke_ok, "detail": smoke_detail},
        }

    if subaction == "kge_status":
        from engine.config.settings import settings as _kge_s

        domain_id = payload.get("domain_id")
        kge_config_info: dict[str, Any] = {}
        if domain_id:
            try:
                spec = domain_loader.load_domain(domain_id)
                if spec.kge:
                    kge_config_info = {
                        "model": spec.kge.model,
                        "embeddingdim": spec.kge.embeddingdim,
                        "training_relations": list(spec.kge.trainingrelations),
                    }
            except Exception:
                kge_config_info = {"error": f"Could not load domain '{domain_id}'"}
        return {
            "status": "ok",
            "kge_enabled": _kge_s.kge_enabled,
            "kge_embedding_dim": _kge_s.kge_embedding_dim,
            "kge_confidence_threshold": _kge_s.kge_confidence_threshold,
            "domain_config": kge_config_info,
        }

    # --- W6-02: GDPR Erasure Endpoint ---
    if subaction == "erase_subject":
        from chassis.errors import FeatureNotEnabled
        from engine.compliance.pii import PIIHandler
        from engine.config.settings import settings as _gdpr_s

        if not _gdpr_s.gdpr_erasure_enabled:
            raise FeatureNotEnabled("GDPR Erasure", flag="GDPR_ERASURE_ENABLED", action="admin", tenant=tenant)
        data_subject_id = _require_key(payload, "data_subject_id", "admin", tenant)
        domain_id = payload.get("domain_id", tenant)
        spec = domain_loader.load_domain(domain_id)

        pii_handler = PIIHandler()

        if _gdpr_s.gdpr_dry_run:
            # Dry-run: compute what WOULD be erased without executing
            try:
                count_result = await graph_driver.execute_query(
                    "MATCH (n {data_subject_id: $dsid}) RETURN count(n) AS cnt",
                    parameters={"dsid": data_subject_id},
                    database=domain_id,
                )
                node_count = count_result[0]["cnt"] if count_result else 0
            except Exception:
                node_count = -1
            return {
                "status": "dry_run",
                "data_subject_id": data_subject_id,
                "dry_run": True,
                "would_affect": {"graph_nodes": node_count},
            }

        # Real erasure
        try:
            result = await pii_handler.erase_subject(
                data_subject_id=data_subject_id,
                graph_driver=graph_driver,
            )
        except Exception as exc:
            raise ExecutionError(
                "GDPR erasure failed",
                action="admin",
                tenant=tenant,
                detail=str(exc),
            ) from exc

        # Flush audit trail for erasure event
        from engine.compliance.audit import AuditLogger

        audit = AuditLogger()
        audit.log_pii_erasure(
            actor=tenant,
            tenant=tenant,
            data_subject_id=data_subject_id,
            detail=f"Erased subject {data_subject_id} in domain {domain_id}",
        )

        return {
            "status": "erased",
            "data_subject_id": data_subject_id,
            "dry_run": False,
            "summary": result,
        }

    # --- W6-03: GDS Job History Exposure ---
    if subaction == "gds_status":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        scheduler = _get_or_create_scheduler(spec, graph_driver)
        history = await scheduler.get_job_history()
        # Summarize per-job last run (prefer job name, fallback to algorithm)
        last_runs: dict[str, Any] = {}
        for entry in reversed(history):
            job_key = entry.get("job") or entry.get("algorithm", "unknown")
            if job_key not in last_runs:
                last_runs[job_key] = {
                    "last_run": entry.get("timestamp"),
                    "status": entry.get("status"),
                }
        return {
            "status": "ok",
            "domain_id": domain_id,
            "last_runs": last_runs,
            "history_count": len(history),
            "recent_history": history[-10:] if len(history) > 10 else history,
        }

    if subaction == "gds_trigger":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        job_name = _require_key(payload, "job_name", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        # Validate algorithm name exists in domain spec
        valid_jobs = {j.name for j in spec.gdsjobs}
        if job_name not in valid_jobs:
            raise ValidationError(
                f"Job '{job_name}' not found in domain spec. Available: {sorted(valid_jobs)}",
                action="admin",
                tenant=tenant,
            )
        scheduler = _get_or_create_scheduler(spec, graph_driver)
        result = await scheduler.trigger_job(job_name)
        return {"status": "triggered", "job": job_name, "result": result}

    if subaction == "gds_health":
        from datetime import UTC, datetime, timedelta

        from engine.config.settings import settings as _gds_s

        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        scheduler = _get_or_create_scheduler(spec, graph_driver)
        history = await scheduler.get_job_history()
        max_staleness = timedelta(hours=_gds_s.gds_max_staleness_hours)
        now = datetime.now(tz=UTC)
        algo_health: dict[str, Any] = {}
        # Build per-job health from most recent entry (prefer job name, fallback to algorithm)
        for entry in reversed(history):
            algo = entry.get("job") or entry.get("algorithm", "unknown")
            if algo in algo_health:
                continue
            ts_str = entry.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    stale = (now - ts) > max_staleness
                except (ValueError, TypeError):
                    stale = True
            else:
                stale = True
            algo_health[algo] = {
                "last_run": ts_str,
                "status": entry.get("status"),
                "stale": stale,
            }
        # Check for algorithms that have never run
        for job in spec.gdsjobs:
            if job.name not in algo_health:
                algo_health[job.name] = {"last_run": None, "status": "never_run", "stale": True}
        all_healthy = all(not v.get("stale") for v in algo_health.values())
        return {
            "status": "healthy" if all_healthy else "degraded",
            "domain_id": domain_id,
            "max_staleness_hours": _gds_s.gds_max_staleness_hours,
            "algorithms": algo_health,
        }

    # --- W6-04: Feature Status ---
    if subaction == "feature_status":
        from engine.config.settings import settings as _fs

        return {
            "status": "ok",
            "feature_gates": {
                # --- Phase 4 / KGE ---
                "kge_enabled": _fs.kge_enabled,
                # --- GDS ---
                "gds_enabled": _fs.gds_enabled,
                # --- Pareto ---
                "pareto_enabled": _fs.pareto_enabled,
                "pareto_weight_discovery_enabled": _fs.pareto_weight_discovery_enabled,
                # --- Wave 1: Invariant Hardening ---
                "domain_strict_validation": _fs.domain_strict_validation,
                "score_clamp_enabled": _fs.score_clamp_enabled,
                "strict_null_gates": _fs.strict_null_gates,
                "param_strict_mode": _fs.param_strict_mode,
                # --- Wave 2: Refinement Scoring ---
                "feedback_enabled": _fs.feedback_enabled,
                "confidence_check_enabled": _fs.confidence_check_enabled,
                "score_normalize": _fs.score_normalize,
                # --- Wave 6: Dormant Feature Activation ---
                "gdpr_erasure_enabled": _fs.gdpr_erasure_enabled,
                "gdpr_dry_run": _fs.gdpr_dry_run,
                "gds_max_staleness_hours": _fs.gds_max_staleness_hours,
            },
        }

    # --- HGKR: Evaluation Endpoint ---
    if subaction == "evaluate":
        return await _handle_evaluate(tenant, payload, graph_driver, domain_loader)

    # --- S2-08: Auto-generate calibration pairs from outcomes ---
    if subaction == "generate_calibration_pairs":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)

        # Read recent outcomes with scores
        outcome_cypher = """
        MATCH (o:TransactionOutcome)
        WHERE o.tenant = $tenant AND o.outcome IN ['success', 'failure']
        RETURN o.match_id AS match_id, o.candidate_id AS candidate_id,
               o.outcome AS outcome, o.value AS score
        ORDER BY o.created_at DESC
        LIMIT 500
        """
        try:
            outcome_records = await graph_driver.execute_query(
                cypher=outcome_cypher,
                parameters={"tenant": tenant},
                database=spec.domain.id,
            )
        except Exception as exc:
            raise ExecutionError(
                "Failed to read outcomes for calibration pair generation",
                action="admin",
                tenant=tenant,
                detail=str(exc),
            ) from exc

        from engine.scoring.hgkr_utils import generate_calibration_pairs

        pairs = generate_calibration_pairs(list(outcome_records))
        return {
            "status": "calibration_pairs_generated",
            "total_pairs": len(pairs),
            "pairs": [
                {
                    "node_a": p.node_a,
                    "node_b": p.node_b,
                    "expected_range": [p.expected_score_min, p.expected_score_max],
                    "label": p.label,
                }
                for p in pairs
            ],
        }

    # --- S2-21: Domain density report ---
    if subaction == "domain_density_report":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)

        # Query graph statistics
        stats_cypher = """
        MATCH (n)
        WITH count(n) AS total_nodes
        OPTIONAL MATCH ()-[r]-()
        WITH total_nodes, count(r) / 2 AS total_edges
        RETURN total_nodes, total_edges
        """
        try:
            stats = await graph_driver.execute_query(
                cypher=stats_cypher,
                parameters={},
                database=spec.domain.id,
            )
        except Exception as exc:
            raise ExecutionError(
                "Failed to read graph statistics",
                action="admin",
                tenant=tenant,
                detail=str(exc),
            ) from exc

        total_nodes = stats[0]["total_nodes"] if stats else 0
        total_edges = stats[0]["total_edges"] if stats else 0

        from engine.scoring.hgkr_utils import DensityReport, generate_density_report

        density_report: DensityReport = generate_density_report(
            domain_id=domain_id,
            total_nodes=total_nodes,
            total_edges=total_edges,
        )
        return {
            "status": "density_report",
            "domain_id": density_report.domain_id,
            "total_nodes": density_report.total_nodes,
            "total_edges": density_report.total_edges,
            "avg_degree": density_report.avg_degree,
            "density_class": density_report.density_class,
            "recommended_sample_size": density_report.recommended_sample_size,
            "recommendations": density_report.recommendations,
        }

    # --- S2-23: Auto-tune aggregation strategies ---
    if subaction == "auto_tune":
        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)

        from engine.scoring.hgkr_utils import build_ablation_configs

        configs = build_ablation_configs(spec.gdsjobs)
        return {
            "status": "auto_tune_configs_generated",
            "domain_id": domain_id,
            "total_configs": len(configs),
            "configs": configs,
            "instructions": (
                "Run 'evaluate' subaction with each config's gds_overrides "
                "to compare AUC across aggregation strategies. Select the "
                "config with highest AUC and apply to domain spec."
            ),
        }

    # --- Milestone 2.2: Pareto Weight Discovery ---
    if subaction == "discover_weights":
        from chassis.errors import FeatureNotEnabled
        from engine.config.settings import settings as _pw_settings

        if not _pw_settings.pareto_weight_discovery_enabled:
            raise FeatureNotEnabled(
                "Pareto Weight Discovery",
                flag="PARETO_WEIGHT_DISCOVERY_ENABLED",
                action="admin",
                tenant=tenant,
            )

        domain_id = _require_key(payload, "domain_id", "admin", tenant)
        spec = domain_loader.load_domain(domain_id)
        n_samples = int(payload.get("n_samples", 50))

        if not spec.decision_arbitration or not spec.decision_arbitration.enabled:
            raise ValidationError(
                "Decision arbitration not enabled in domain spec",
                action="admin",
                tenant=tenant,
            )

        dimension_names = [obj.dimension for obj in spec.decision_arbitration.pareto_config.objectives]

        if not dimension_names:
            raise ValidationError(
                "No Pareto objectives defined in decision_arbitration.pareto_config",
                action="admin",
                tenant=tenant,
            )

        # Read outcome history from Neo4j
        outcome_cypher = """
        MATCH (o:TransactionOutcome)
        WHERE o.tenant = $tenant AND o.dimension_scores IS NOT NULL
        RETURN o.dimension_scores AS dimension_scores,
               o.was_selected AS was_selected
        ORDER BY o.created_at DESC
        LIMIT 1000
        """
        try:
            raw_outcomes = await graph_driver.execute_query(
                cypher=outcome_cypher,
                parameters={"tenant": tenant},
                database=spec.domain.id,
            )
        except Exception as exc:
            raise ExecutionError(
                "Failed to read outcomes for weight discovery",
                action="admin",
                tenant=tenant,
                detail=str(exc),
            ) from exc

        # Convert to the format expected by discover_pareto_weights
        import json as _json

        outcome_history: list[dict[str, Any]] = []
        for rec in raw_outcomes:
            ds = rec.get("dimension_scores")
            if isinstance(ds, str):
                try:
                    ds = _json.loads(ds)
                except (ValueError, TypeError):
                    continue
            if not isinstance(ds, dict):
                continue
            outcome_history.append(
                {
                    "dimension_scores": {k: float(v) for k, v in ds.items()},
                    "was_selected": bool(rec.get("was_selected", False)),
                }
            )

        if len(outcome_history) < 10:
            return {
                "status": "insufficient_data",
                "error": "Insufficient outcome history for weight discovery",
                "min_required": 10,
                "current_count": len(outcome_history),
            }

        from engine.scoring.weight_discovery import adaptive_weight_discovery

        weight_vectors = await adaptive_weight_discovery(
            dimension_names=dimension_names,
            outcome_history=outcome_history,
            n_samples=n_samples,
        )

        return {
            "status": "weights_discovered",
            "discovered_weights": [
                {
                    "weights": wv.weights,
                    "ndcg_score": round(wv.ndcg_score, 6),
                    "diversity_score": round(wv.diversity_score, 6),
                    "coverage_score": round(wv.coverage_score, 6),
                }
                for wv in weight_vectors
            ],
            "front_size": len(weight_vectors),
            "outcome_history_size": len(outcome_history),
        }

    raise ValidationError(f"Unknown admin subaction: {subaction!r}", action="admin", tenant=tenant)


async def _handle_evaluate(
    tenant: str,
    payload: dict[str, Any],
    graph_driver: GraphDriver,
    domain_loader: DomainPackLoader,
) -> dict[str, Any]:
    """Evaluate scoring quality against a labeled test set.

    Computes precision@K, recall@K, F1@K, and NDCG@K for a batch
    of test cases run through handle_match.

    Payload:
        - domain_id: str — domain to evaluate against
        - test_set: list[dict] — each with "query", "match_direction",
          "expected_ids" (list[str] of known-good candidate entity_ids)
        - k: int — top-K for evaluation (default 10)
        - weights: dict — optional scoring weight overrides
        - ablation: dict — optional dimension ablation overrides
    """
    import math

    domain_id = _require_key(payload, "domain_id", "admin", tenant)
    test_set = _require_key(payload, "test_set", "admin", tenant)
    k = int(payload.get("k", 10))
    weight_overrides = payload.get("weights", {})

    if not isinstance(test_set, list) or len(test_set) == 0:
        raise ValidationError(
            "test_set must be a non-empty list",
            action="admin",
            tenant=tenant,
        )

    per_case_results: list[dict[str, Any]] = []
    total_precision = 0.0
    total_recall = 0.0
    total_ndcg = 0.0

    for case_idx, case in enumerate(test_set):
        query = case.get("query", {})
        match_direction = case.get("match_direction", "")
        expected_ids = set(case.get("expected_ids", []))

        if not expected_ids:
            per_case_results.append({"case_index": case_idx, "skipped": True, "reason": "no expected_ids"})
            continue

        match_payload: dict[str, Any] = {
            "query": query,
            "match_direction": match_direction,
            "top_n": k,
        }
        if weight_overrides:
            match_payload["weights"] = weight_overrides

        try:
            match_result = await handle_match(domain_id, match_payload)
        except Exception as exc:
            per_case_results.append({"case_index": case_idx, "error": str(exc)})
            continue

        candidates = match_result.get("candidates", [])
        returned_ids = []
        for c in candidates[:k]:
            if isinstance(c, dict):
                cand_node = c.get("candidate", {})
                if isinstance(cand_node, dict):
                    returned_ids.append(str(cand_node.get("entity_id", "")))
                else:
                    returned_ids.append("")
            else:
                returned_ids.append("")

        # Precision@K: fraction of returned candidates that are relevant
        relevant_returned = sum(1 for rid in returned_ids if rid in expected_ids)
        precision = relevant_returned / len(returned_ids) if returned_ids else 0.0

        # Recall@K: fraction of relevant candidates that were returned
        recall = relevant_returned / len(expected_ids) if expected_ids else 0.0

        # NDCG@K: normalized discounted cumulative gain
        dcg = 0.0
        for rank, rid in enumerate(returned_ids, start=1):
            if rid in expected_ids:
                dcg += 1.0 / math.log2(rank + 1)
        # Ideal DCG: all relevant items at top positions
        ideal_count = min(len(expected_ids), k)
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
        ndcg = dcg / idcg if idcg > 0 else 0.0

        total_precision += precision
        total_recall += recall
        total_ndcg += ndcg

        per_case_results.append(
            {
                "case_index": case_idx,
                "precision_at_k": round(precision, 4),
                "recall_at_k": round(recall, 4),
                "ndcg_at_k": round(ndcg, 4),
                "returned_count": len(returned_ids),
                "relevant_returned": relevant_returned,
            }
        )

    evaluated_count = sum(1 for r in per_case_results if "precision_at_k" in r)
    avg_precision = total_precision / evaluated_count if evaluated_count > 0 else 0.0
    avg_recall = total_recall / evaluated_count if evaluated_count > 0 else 0.0
    avg_ndcg = total_ndcg / evaluated_count if evaluated_count > 0 else 0.0
    f1 = (2 * avg_precision * avg_recall / (avg_precision + avg_recall)) if (avg_precision + avg_recall) > 0 else 0.0

    return {
        "status": "evaluation_complete",
        "k": k,
        "test_cases": len(test_set),
        "evaluated": evaluated_count,
        "aggregate": {
            "precision_at_k": round(avg_precision, 4),
            "recall_at_k": round(avg_recall, 4),
            "f1_at_k": round(f1, 4),
            "ndcg_at_k": round(avg_ndcg, 4),
        },
        "per_case": per_case_results,
    }


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
    state = get_state()
    domain_id = spec.domain.id
    if domain_id not in state.gds_schedulers:
        scheduler = GDSScheduler(spec, driver)
        scheduler.register_jobs()
        scheduler.start()
        state.gds_schedulers[domain_id] = scheduler
    result: GDSScheduler = state.gds_schedulers[domain_id]
    return result


async def handle_outcomes(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Write TransactionOutcome nodes with match fingerprint and RESULTED_IN edges."""
    graph_driver, domain_loader = _require_deps()
    _validate_tenant_access(tenant, "outcomes")

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
    _enforce_capability(tenant, "outcomes", domain_spec)
    outcome_id = f"out_{uuid.uuid4().hex[:12]}"

    # R3: Causal validation for RESULTED_IN edge
    if domain_spec.causal.enabled:
        from engine.causal.causal_validator import CausalEdgeRuntimeValidator

        validator = CausalEdgeRuntimeValidator(domain_spec.causal)
        edge_record = {
            "source_ts": payload.get("source_ts"),
            "target_ts": payload.get("target_ts"),
            "confidence": payload.get("confidence"),
        }
        _valid, rejected = validator.validate_batch([edge_record], "RESULTED_IN")
        if rejected:
            logger.info(
                "Causal validation rejected RESULTED_IN edge: %s",
                rejected[0].get("rejection_reason"),
            )

    # R5: Extract match fingerprint from payload
    fingerprint = payload.get("fingerprint", {})
    active_dimensions = fingerprint.get("active_dimensions", [])
    dimension_weights = fingerprint.get("dimension_weights", {})
    gates_passed = fingerprint.get("gates_passed", [])
    match_direction = fingerprint.get("match_direction")
    candidate_count = fingerprint.get("candidate_count", 0)

    cypher = """
    CREATE (o:TransactionOutcome {
        outcome_id: $outcome_id, match_id: $match_id,
        candidate_id: $candidate_id, outcome: $outcome,
        value: $value, created_at: datetime(), tenant: $tenant,
        domain_id: $domain_id,
        active_dimensions: $active_dimensions,
        dimension_weights: $dimension_weights,
        gates_passed: $gates_passed,
        match_direction: $match_direction,
        candidate_count: $candidate_count
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
                "domain_id": domain_spec.domain.id,
                "active_dimensions": active_dimensions,
                "dimension_weights": str(dimension_weights),
                "gates_passed": gates_passed,
                "match_direction": match_direction,
                "candidate_count": candidate_count,
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

    # R6: Counterfactual generation for negative outcomes
    if domain_spec.counterfactual.enabled and outcome == "failure":
        try:
            from engine.causal.counterfactual import CounterfactualGenerator

            generator = CounterfactualGenerator(
                counterfactual_spec=domain_spec.counterfactual,
                graph_driver=graph_driver,
                domain_id=domain_spec.domain.id,
            )
            await generator.generate_for_outcome(outcome_id)
        except Exception:
            logger.warning("Counterfactual generation failed for %s", outcome_id, exc_info=True)

    compliance = _get_compliance_engine(domain_spec)
    if compliance.enabled:
        compliance.log_outcome(tenant=tenant, outcome_id=outcome_id, outcome=outcome)

    response: dict[str, Any] = {"status": "recorded", "outcome_id": outcome_id}

    # Feedback loop: propagate outcome to signal weights and score adjustments
    if domain_spec.feedbackloop.enabled:
        from engine.feedback.convergence import ConvergenceLoop

        outcome_data = {
            "outcome_id": outcome_id,
            "match_id": match_id,
            "candidate_id": candidate_id,
            "outcome": outcome,
            "value": payload.get("value"),
        }
        loop = ConvergenceLoop(graph_driver, domain_spec)
        feedback_metadata = await loop.on_outcome_recorded(outcome_data)
        response["feedback"] = feedback_metadata

    # Causal edge creation: auto-create causal chain from outcome
    if domain_spec.causal.enabled:
        from engine.causal.causal_compiler import CausalCompiler

        compiler = CausalCompiler(domain_spec)
        for edge_spec in domain_spec.causal.causal_edges:
            if edge_spec.edge_type == "RESULTED_IN":
                edge_cypher = compiler.compile_causal_edge_create(edge_spec)
                try:
                    await graph_driver.execute_query(
                        cypher=edge_cypher,
                        parameters={
                            "source_id": candidate_id,
                            "target_id": outcome_id,
                            "confidence": 1.0,
                            "mechanism": f"outcome_{outcome}",
                        },
                        database=domain_spec.domain.id,
                    )
                except Exception:
                    logger.warning("Causal edge creation failed for outcome=%s", outcome_id, exc_info=True)

        # Compute attribution if enabled
        if domain_spec.causal.attribution_enabled:
            from engine.causal.attribution import AttributionCalculator

            attr_calc = AttributionCalculator(graph_driver, domain_spec)
            try:
                attribution = await attr_calc.compute_attribution(outcome_id)
                response["attribution"] = attribution
            except Exception:
                logger.warning("Attribution calculation failed for outcome=%s", outcome_id, exc_info=True)

    return response


async def handle_resolve(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Entity resolution: create RESOLVED_FROM edge between duplicate entities.

    When semantic_registry is enabled, uses multi-signal similarity scoring
    to automatically find and merge duplicates. Otherwise, falls back to
    manual RESOLVED_FROM edge creation.
    """
    graph_driver, domain_loader = _require_deps()
    _validate_tenant_access(tenant, "resolve")

    entity_type = _require_key(payload, "entity_type", "resolve", tenant)
    domain_spec = domain_loader.load_domain(tenant)
    _enforce_capability(tenant, "resolve", domain_spec)

    # R8: Semantic registry-based resolution
    if domain_spec.semantic_registry.enabled and entity_type in domain_spec.semantic_registry.entity_labels:
        from engine.resolution.resolver import EntityResolver

        resolver = EntityResolver(
            registry_spec=domain_spec.semantic_registry,
            graph_driver=graph_driver,
            domain_id=domain_spec.domain.id,
        )

        # Batch mode: resolve all entities of this type
        if payload.get("mode") == "batch":
            try:
                result = await resolver.resolve_batch(
                    entity_label=entity_type,
                    threshold=payload.get("threshold"),
                )
            except Exception as exc:
                raise ExecutionError(
                    "Batch entity resolution failed",
                    action="resolve",
                    tenant=tenant,
                    detail=str(exc),
                ) from exc
            else:
                return {"status": "batch_resolved", **result}

        # Single entity mode
        source_id = _require_key(payload, "source_id", "resolve", tenant)
        try:
            result = await resolver.resolve_entity(
                entity_id=source_id,
                entity_label=entity_type,
            )
        except Exception as exc:
            raise ExecutionError(
                "Entity resolution failed",
                action="resolve",
                tenant=tenant,
                detail=str(exc),
            ) from exc
        else:
            return {"status": "resolved", **result}

    # Legacy manual resolution
    source_id = _require_key(payload, "source_id", "resolve", tenant)
    target_id = _require_key(payload, "target_id", "resolve", tenant)
    confidence = payload.get("confidence", 1.0)
    signal = payload.get("signal", "manual")

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


# Named status constants — never use string literals for health evaluation
_HEALTH_OK = "ok"
_HEALTH_NEO4J_CONN_FAILED = "error: connection_failed"
_HEALTH_DOMAIN_TENANT_MISSING = "ok: tenant not found; fallback available"
_HEALTH_DOMAIN_NO_PACKS = "error: no_domains_found"
_HEALTH_DOMAIN_CONFIG_INVALID = "error: config_invalid"


async def handle_health(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Health check: Neo4j connectivity and domain spec validity."""
    from engine.config.loader import DomainNotFoundError

    graph_driver, domain_loader = _require_deps()
    checks: dict[str, str] = {"neo4j": "unknown", "domain_spec": "unknown"}

    try:
        # Query the 'neo4j' default database — 'system' only accepts DDL (SHOW/CREATE DATABASE)
        await graph_driver.execute_query("RETURN 1 AS ping", database="neo4j")
        checks["neo4j"] = _HEALTH_OK
    except Exception:
        checks["neo4j"] = _HEALTH_NEO4J_CONN_FAILED

    try:
        domain_loader.load_domain(tenant)
        checks["domain_spec"] = _HEALTH_OK
    except DomainNotFoundError:
        # Tenant spec absent — check whether any domain packs are loaded at all.
        # A generic /v1/health probe (tenant="default") should not fail when the
        # deployment is healthy but the "default" tenant hasn't been seeded.
        available = domain_loader.list_domains()
        if available:
            checks["domain_spec"] = f"{_HEALTH_DOMAIN_TENANT_MISSING}: {available}"
        else:
            checks["domain_spec"] = _HEALTH_DOMAIN_NO_PACKS
    except Exception:
        # Unexpected loader error — real configuration problem, not just missing tenant
        checks["domain_spec"] = _HEALTH_DOMAIN_CONFIG_INVALID

    neo4j_ok = checks["neo4j"] == _HEALTH_OK
    domain_ok = checks["domain_spec"] == _HEALTH_OK
    overall = "healthy" if (neo4j_ok and domain_ok) else "degraded"
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
    _validate_tenant_access(tenant, "enrich")
    domain_spec = domain_loader.load_domain(tenant)
    _enforce_capability(tenant, "enrich", domain_spec)

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
    """Register all 8 action handlers with a legacy chassis router interface.

    The primary registration path is via chassis.actions._init_engine()
    which builds the handler dict directly. This function exists for
    chassis implementations that use a router.register_handler() pattern.
    """
    chassis_router.register_handler("match", handle_match)
    chassis_router.register_handler("sync", handle_sync)
    chassis_router.register_handler("admin", handle_admin)
    chassis_router.register_handler("outcomes", handle_outcomes)
    chassis_router.register_handler("resolve", handle_resolve)
    chassis_router.register_handler("health", handle_health)
    chassis_router.register_handler("healthcheck", handle_healthcheck)
    chassis_router.register_handler("enrich", handle_enrich)
    logger.info("Registered 8 action handlers: match, sync, admin, outcomes, resolve, health, healthcheck, enrich")
