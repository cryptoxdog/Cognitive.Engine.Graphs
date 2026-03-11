"""Public entrypoint runtime for the L9 Constellation Runtime v1.0.0."""
import time
from constellation.types import (
    PacketEnvelope, normalize_packet, TerminalResult, ConstellationError, _uid
)
from constellation.action_registry import ACTION_MAP, get_action_handler
from constellation.node_registry import list_nodes, get_node
from constellation.router import route_packet

_DOMAINS: set[str] = set()
_METRICS: dict = {
    "request_count": 0,
    "request_duration_ms_total": 0.0,
    "node_hop_count_total": 0,
    "action_errors": 0,
    "token_usage_total": 0,
    "cost_total": 0.0,
}

def register_domain(domain: str):
    _DOMAINS.add(domain)

def execute(request: dict) -> dict:
    start = time.time()
    _METRICS["request_count"] += 1
    try:
        domain = request.get("domain")
        action = request.get("action")
        if not domain or domain not in _DOMAINS:
            raise ConstellationError(f"Invalid domain: {domain}", status="rejected")
        if not action or action not in ACTION_MAP:
            raise ConstellationError(f"Invalid action: {action}", status="rejected")

        packet = normalize_packet(request)
        result, hops = route_packet(packet)

        elapsed = (time.time() - start) * 1000
        _METRICS["request_duration_ms_total"] += elapsed
        _METRICS["node_hop_count_total"] += len(hops)

        meta = {
            "trace_id": packet.trace_id,
            "execution_ms": round(elapsed, 2),
            "node_hops": hops,
        }
        if request.get("payload", {}).get("_cost") is not None:
            meta["cost"] = request["payload"]["_cost"]
        if request.get("payload", {}).get("_token_usage") is not None:
            meta["token_usage"] = request["payload"]["_token_usage"]

        return {
            "status": result.status,
            "action": action,
            "domain": domain,
            "data": result.data,
            "meta": meta,
        }
    except ConstellationError as exc:
        elapsed = (time.time() - start) * 1000
        _METRICS["action_errors"] += 1
        _METRICS["request_duration_ms_total"] += elapsed
        return {
            "status": exc.status,
            "action": request.get("action", "unknown"),
            "domain": request.get("domain", "unknown"),
            "data": {"error": str(exc)},
            "meta": {"trace_id": request.get("trace_id", _uid()),
                     "execution_ms": round(elapsed, 2), "node_hops": []},
        }

def health() -> dict:
    nodes = list_nodes()
    return {
        "status": "healthy",
        "nodes": len(nodes),
        "nodes_healthy": sum(1 for n in nodes if n.health_check_enabled),
        "actions_registered": len(ACTION_MAP),
        "domains_registered": len(_DOMAINS),
    }

def metrics() -> dict:
    return dict(_METRICS)

def validate_startup():
    errors = []
    if not ACTION_MAP:
        errors.append("action_registry is empty")
    nodes = list_nodes()
    if not nodes:
        errors.append("node_registry is empty")
    node_names = {n.node_name for n in nodes}
    for action, node_name in ACTION_MAP.items():
        if node_name not in node_names:
            errors.append(f"action '{action}' maps to unregistered node '{node_name}'")
    for node in nodes:
        for sa in node.supported_actions:
            if sa not in ACTION_MAP:
                errors.append(f"node '{node.node_name}' supports action '{sa}' not in ACTION_MAP")
    if errors:
        raise RuntimeError("Startup validation failed:\n  " + "\n  ".join(errors))
