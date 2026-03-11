"""Packet routing between internal nodes for the L9 Constellation Runtime."""
import time
from constellation.types import (
    PacketEnvelope, TraceEntry, TerminalResult, ConstellationError, _uid
)
from constellation.action_registry import ACTION_MAP, get_action_handler
from constellation.node_registry import get_node

def resolve_initial_node(action: str) -> str:
    if action not in ACTION_MAP:
        raise ConstellationError(f"No node registered for action: {action}", status="rejected")
    return ACTION_MAP[action]

def append_trace(packet: PacketEnvelope, entry: TraceEntry):
    packet.trace.append(entry)

def route_packet(packet: PacketEnvelope, *, max_hops: int = 20, timeout_ms: float = 60000):
    """Route a packet through internal nodes until a terminal condition."""
    start = time.time()
    current_action = packet.action
    hops: list[str] = []

    for _ in range(max_hops):
        elapsed_ms = (time.time() - start) * 1000
        if elapsed_ms > timeout_ms:
            append_trace(packet, TraceEntry(node="router", action=current_action, status="timeout"))
            raise ConstellationError("Execution timeout exceeded", status="timeout")

        node_name = resolve_initial_node(current_action)
        node_rec = get_node(node_name)
        handler = get_action_handler(current_action)
        hops.append(node_name)

        hop_start = time.time()
        try:
            result = handler(packet)
        except ConstellationError:
            raise
        except Exception as exc:
            append_trace(packet, TraceEntry(
                node=node_name, action=current_action, status="error",
                latency_ms=(time.time() - hop_start) * 1000))
            raise ConstellationError(str(exc), status="error")

        hop_latency = (time.time() - hop_start) * 1000
        if isinstance(result, TerminalResult):
            append_trace(packet, TraceEntry(
                node=node_name, action=current_action, status="completed",
                latency_ms=hop_latency))
            return result, hops

        if isinstance(result, PacketEnvelope):
            append_trace(packet, TraceEntry(
                node=node_name, action=current_action, status="forwarded",
                latency_ms=hop_latency))
            current_action = result.action
            packet.payload = result.payload
            continue

        append_trace(packet, TraceEntry(
            node=node_name, action=current_action, status="completed",
            latency_ms=hop_latency))
        return TerminalResult(data=result if isinstance(result, dict) else {}), hops

    raise ConstellationError("Max internal hops exceeded", status="error")
