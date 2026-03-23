"""
L9 Cursor LangGraph Integration
Version: 1.0.0

Defines Cursor-specific LangGraph state and nodes for orchestrating planning,
memory writes, memory search, error handling, and governance decision gating.

Follows Research Factory pattern: Pydantic BaseModel state, async node functions.
"""

from __future__ import annotations

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Langgraph",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-11T18:13:39Z",
    "updated_at": "2026-01-17T23:47:56Z",
    "layer": "intelligence",
    "domain": "data_models",
    "module_name": "cursor_langgraph",
    "type": "schema",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": ["working_memory"],
        "imported_by": [
            "agents.cursor.integrations.cursor_executor",
            "agents.cursor.integrations.cursor_gateway",
            "api.server",
            "memory.checkpoint.cursor_checkpoint_manager",
            "tests.integration.test_cursor_langgraph_integration",
        ],
    },
}
# ============================================================================

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from core.config_constants import DEFAULT_SEARCH_SCOPES
from core.decorators import must_stay_async
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# =============================================================================
# State Model
# =============================================================================


class CursorAgentState(BaseModel):
    """
    LangGraph state model for Cursor agent execution.

    Follows ResearchState pattern: Pydantic BaseModel for validation and serialization.
    State flows through nodes and accumulates results.
    """

    # === Identity ===
    thread_id: str | None = Field(None, description="Thread/conversation ID")
    task_id: str | None = Field(None, description="Task identifier")

    # === Input ===
    messages: list[dict[str, Any]] = Field(default_factory=list, description="Serialized message history")
    task: str | None = Field(None, description="Current task description")
    task_status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="Task execution status"
    )

    # === Context ===
    current_file: str | None = Field(None, description="Currently focused file path")
    selected_code: str | None = Field(None, description="Selected code snippet")
    project_id: str | None = Field(None, description="Project identifier")

    # === Reasoning & Decisions ===
    reasoning_trace: list[dict[str, Any]] = Field(default_factory=list, description="Structured reasoning blocks")
    decisions: list[dict[str, Any]] = Field(default_factory=list, description="Decisions made during execution")
    tool_results: list[dict[str, Any]] = Field(default_factory=list, description="Results from tool executions")
    search_hits: list[dict[str, Any]] = Field(default_factory=list, description="Memory search results")

    # === Checkpoint & Governance ===
    last_checkpoint_id: str | None = Field(None, description="Last checkpoint ID (PostgresSaver)")
    last_packet_id: UUID | None = Field(None, description="Last PacketEnvelope ID (dual checkpoint)")
    approval_status: str | None = Field(None, description="Current Igor approval status")
    approval_id: str | None = Field(None, description="Pending approval request ID")

    # === Error Handling ===
    errors: list[dict[str, Any]] = Field(default_factory=list, description="Error records with context")
    recovery_suggestions: list[str] = Field(default_factory=list, description="Suggested recovery actions")

    model_config = {"extra": "allow"}


# =============================================================================
# Node Classes
# =============================================================================


class CursorPlanningNode:
    """
    Planning node: refines task and enriches state with structured reasoning.

    Does NOT write to memory; only plans and enriches state.
    """

    def __init__(self, llm_provider: Any | None = None):
        """
        Initialize planning node.

        Args:
            llm_provider: Optional LLM provider for task refinement
        """
        self._llm_provider = llm_provider

    @must_stay_async("LangGraph node protocol")
    async def __call__(self, state: CursorAgentState) -> CursorAgentState:
        """
        Execute planning node.

        Args:
            state: Current agent state

        Returns:
            Updated state with refined task and reasoning trace
        """
        logger.info("CursorPlanningNode: Planning task", task=state.task)

        # Refine task if needed
        refined_task = state.task
        if state.task and state.task_status != "completed":
            # Simple refinement: could be enhanced with LLM
            refined_task = state.task.strip()

        # Create reasoning block
        reasoning_block = {
            "step_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "reasoning_type": "planning",
            "content": f"Planning task: {refined_task}",
            "confidence": 0.8,
        }

        # Update state
        return state.model_copy(
            update={
                "task": refined_task,
                "task_status": "running",
                "reasoning_trace": [*state.reasoning_trace, reasoning_block],
            }
        )


class CursorMemoryWriteNode:
    """
    Memory write node: writes decisions and errors to memory substrate.

    Calls CursorMemoryGateway.write_decision() and/or .write_error().
    Updates state with written packet IDs.
    """

    def __init__(self, memory_gateway: Any):
        """
        Initialize memory write node.

        Args:
            memory_gateway: CursorMemoryGateway instance
        """
        self._gateway = memory_gateway

    async def __call__(self, state: CursorAgentState) -> CursorAgentState:
        """
        Execute memory write node.

        Args:
            state: Current agent state

        Returns:
            Updated state with written packet IDs
        """
        logger.info("CursorMemoryWriteNode: Writing to memory")

        packet_ids = []

        # Write decisions
        if state.decisions:
            for decision in state.decisions:
                try:
                    packet_id = await self._gateway.write_decision(state)
                    packet_ids.append(packet_id)
                    logger.debug("Decision written", packet_id=packet_id)
                except Exception as e:
                    logger.error("Failed to write decision", error=str(e))
                    state.errors.append(
                        {
                            "type": "memory_write_error",
                            "error": str(e),
                            "decision": decision,
                        }
                    )

        # Write errors
        if state.errors:
            for _error in state.errors:
                try:
                    packet_id = await self._gateway.write_error(state)
                    packet_ids.append(packet_id)
                    logger.debug("Error written", packet_id=packet_id)
                except Exception as e:
                    logger.error("Failed to write error", error=str(e))

        # Update state with last packet ID
        last_packet_id = packet_ids[-1] if packet_ids else None

        return state.model_copy(
            update={
                "last_packet_id": last_packet_id,
            }
        )


class CursorMemorySearchNode:
    """
    Memory search node: searches memory substrate and writes hits into state.

    Calls CursorMemoryGateway.search_memory().
    """

    def __init__(self, memory_gateway: Any):
        """
        Initialize memory search node.

        Args:
            memory_gateway: CursorMemoryGateway instance
        """
        self._gateway = memory_gateway

    @must_stay_async("callers use await")
    async def __call__(self, state: CursorAgentState) -> CursorAgentState:
        """
        Execute memory search node.

        Args:
            state: Current agent state

        Returns:
            Updated state with search hits
        """
        logger.info("CursorMemorySearchNode: Searching memory")

        # Build search query from task
        query = state.task or ""
        if not query:
            logger.warning("No task for memory search")
            return state

        try:
            # ADR-0098: search scopes from config_constants
            hits = await self._gateway.search_memory(
                query=query,
                scope=DEFAULT_SEARCH_SCOPES,
                project_id=state.project_id or "default",
                limit=10,
            )

            logger.info("Memory search completed", hits_count=len(hits))

            return state.model_copy(
                update={
                    "search_hits": hits,
                    "tool_results": [
                        *state.tool_results,
                        {"type": "memory_search", "hits": hits},
                    ],
                }
            )
        except Exception as e:
            logger.error("Memory search failed", error=str(e))
            return state.model_copy(
                update={
                    "errors": [
                        *state.errors,
                        {"type": "memory_search_error", "error": str(e)},
                    ],
                }
            )


class CursorErrorRecoveryNode:
    """
    Error recovery node: logs errors, queries past fixes, updates state with recovery suggestions.
    """

    def __init__(self, memory_gateway: Any):
        """
        Initialize error recovery node.

        Args:
            memory_gateway: CursorMemoryGateway instance for searching past fixes
        """
        self._gateway = memory_gateway

    @must_stay_async("callers use await")
    async def __call__(self, state: CursorAgentState) -> CursorAgentState:
        """
        Execute error recovery node.

        Args:
            state: Current agent state

        Returns:
            Updated state with recovery suggestions
        """
        if not state.errors:
            return state

        logger.info("CursorErrorRecoveryNode: Processing errors", error_count=len(state.errors))

        recovery_suggestions = []

        for error in state.errors:
            error_type = error.get("type", "unknown")
            error_msg = error.get("error", "")

            # Log error
            logger.error("Error detected", type=error_type, error=error_msg)

            # Search for past fixes
            try:
                query = f"fix {error_type} {error_msg[:50]}"
                hits = await self._gateway.search_memory(
                    query=query,
                    scope=DEFAULT_SEARCH_SCOPES,
                    project_id=state.project_id or "default",
                    limit=5,
                )

                if hits:
                    recovery_suggestions.append(f"Found {len(hits)} similar fixes in memory for {error_type}")
            except Exception as e:
                logger.warning("Failed to search for fixes", error=str(e))

        # Add reasoning block
        reasoning_block = {
            "step_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "reasoning_type": "error_recovery",
            "content": f"Recovery suggestions: {', '.join(recovery_suggestions)}",
            "confidence": 0.7,
        }

        return state.model_copy(
            update={
                "recovery_suggestions": recovery_suggestions,
                "reasoning_trace": [*state.reasoning_trace, reasoning_block],
            }
        )


class CursorDecisionGateNode:
    """
    Decision gate node: invokes governance approval gate for high-impact decisions.

    Pauses/resumes graph execution depending on Igor's decision.
    """

    def __init__(self, approval_gate: Any):
        """
        Initialize decision gate node.

        Args:
            approval_gate: Approval gate functions (is_high_impact_decision, escalate_to_igor, etc.)
        """
        self._approval_gate = approval_gate

    @must_stay_async("callers use await")
    async def __call__(self, state: CursorAgentState) -> CursorAgentState:
        """
        Execute decision gate node.

        Args:
            state: Current agent state

        Returns:
            Updated state with approval status
        """
        logger.info("CursorDecisionGateNode: Checking decisions")

        if not state.decisions:
            return state

        # Check last decision
        last_decision = state.decisions[-1]

        # Check if high-impact
        is_high_impact = self._approval_gate.is_high_impact_decision(last_decision)

        if not is_high_impact:
            logger.debug("Decision is not high-impact, proceeding")
            return state.model_copy(update={"approval_status": "not_required"})

        # Escalate to Igor
        logger.info("High-impact decision detected, escalating to Igor")
        try:
            escalation_result = await self._approval_gate.escalate_to_igor(
                decision_packet=None  # TODO(GMP-120): Build PacketEnvelope from decision
            )

            # Handle governance result
            return self._approval_gate.handle_governance_result(escalation_result, state)

        except Exception as e:
            logger.error("Approval escalation failed", error=str(e))
            return state.model_copy(
                update={
                    "approval_status": "error",
                    "errors": [
                        *state.errors,
                        {"type": "approval_error", "error": str(e)},
                    ],
                }
            )


# =============================================================================
# Graph Construction
# =============================================================================


def build_cursor_langgraph(
    config: Any,  # CursorLangGraphConfig
    deps: Any,  # CursorGraphDependencies
) -> Any:
    """
    Build Cursor LangGraph application.

    Args:
        config: CursorLangGraphConfig instance
        deps: Dependencies (memory_gateway, approval_gate, etc.)

    Returns:
        Compiled LangGraph application
    """
    logger.info("Building Cursor LangGraph")

    # Initialize nodes
    planning_node = CursorPlanningNode()
    memory_write_node = CursorMemoryWriteNode(deps.memory_gateway)
    memory_search_node = CursorMemorySearchNode(deps.memory_gateway)
    error_recovery_node = CursorErrorRecoveryNode(deps.memory_gateway)
    decision_gate_node = CursorDecisionGateNode(deps.approval_gate)

    # Build graph
    graph = StateGraph(CursorAgentState)

    # Add nodes
    graph.add_node("planning", planning_node)
    graph.add_node("memory_write", memory_write_node)
    graph.add_node("memory_search", memory_search_node)
    graph.add_node("error_recovery", error_recovery_node)
    graph.add_node("decision_gate", decision_gate_node)

    # Define edges
    graph.add_edge(START, "planning")
    graph.add_edge("planning", "memory_search")
    graph.add_edge("memory_search", "decision_gate")
    graph.add_edge("decision_gate", "memory_write")
    graph.add_edge("memory_write", "error_recovery")
    graph.add_edge("error_recovery", END)

    # Compile with checkpoint manager (if provided)
    if hasattr(deps, "checkpoint_manager") and deps.checkpoint_manager:
        # TODO(GMP-121): Wire checkpoint manager
        pass

    return graph.compile()


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-024",
    "governance_level": "high",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": ["core.decorators"],
    "tags": [
        "async",
        "data-models",
        "debugging",
        "intelligence",
        "logging",
        "messaging",
        "pydantic",
        "schema",
        "tracing",
        "validation",
    ],
    "keywords": [
        "agent",
        "build",
        "cursor",
        "decision",
        "gate",
        "governance",
        "langgraph",
        "memory",
    ],
    "business_value": "Provides cursor langgraph components including CursorAgentState, CursorPlanningNode, CursorMemoryWriteNode",
    "last_modified": "2026-01-17T23:47:56Z",
    "modified_by": "L9_Codegen_Engine",
    "change_summary": "Initial generation with DORA compliance",
}
# ============================================================================
# L9 DORA BLOCK - AUTO-UPDATED - DO NOT EDIT
# Runtime execution trace - updated automatically on every execution
# ============================================================================
__l9_trace__ = {
    "trace_id": "",
    "task": "",
    "timestamp": "",
    "patterns_used": [],
    "graph": {"nodes": [], "edges": []},
    "inputs": {},
    "outputs": {},
    "metrics": {"confidence": "", "errors_detected": [], "stability_score": ""},
}
# ============================================================================
# END L9 DORA BLOCK
# ============================================================================
