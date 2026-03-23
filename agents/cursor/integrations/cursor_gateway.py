"""
L9 Cursor Memory Gateway
Version: 2.0.0

Safe gateway for Cursor to read/write through the Memory Substrate using
PacketEnvelope v2.0.0, enforcing scope constraints.

Cursor can only access "developer" and "global" scopes.

LGRAPH-006: Implemented load_checkpoint() via search_packets_by_thread
LGRAPH-007: Implemented search_memory() via semantic_search
"""

from __future__ import annotations

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Gateway",
    "module_version": "2.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-11T18:13:39Z",
    "updated_at": "2026-01-17T23:47:56Z",
    "layer": "intelligence",
    "domain": "error_handling",
    "module_name": "cursor_gateway",
    "type": "exception",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": ["semantic_memory", "working_memory"],
        "imported_by": [
            "agents.cursor.integrations.cursor_executor",
            "api.server",
            "memory.checkpoint.cursor_checkpoint_manager",
            "tests.integration.test_cursor_langgraph_integration",
        ],
    },
}
# ============================================================================

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from core.decorators import must_stay_async
from core.schemas import PacketEnvelopeIn, SemanticSearchRequest
from memory.governance_gate import build_governance_context, governance_context

if TYPE_CHECKING:
    from memory.substrate_service import MemorySubstrateService

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class CursorScopeViolationError(Exception):
    """Raised when Cursor attempts to access disallowed scope."""


# =============================================================================
# Gateway Class
# =============================================================================


class CursorMemoryGateway:
    """
    Safe gateway for Cursor to interact with L9 Memory Substrate.

    Enforces scope constraints: Cursor can only access "developer" and "global" scopes.
    All operations go through MemorySubstrateService for full pipeline processing.
    """

    # Allowed scopes for Cursor
    ALLOWED_SCOPES = {"developer", "global"}

    def __init__(self, substrate_service: MemorySubstrateService):
        """
        Initialize Cursor memory gateway.

        Args:
            substrate_service: MemorySubstrateService for all memory operations
        """
        self._substrate_service = substrate_service
        logger.info("CursorMemoryGateway initialized with MemorySubstrateService")

    def _validate_scope(self, scope: str | list[str]) -> None:
        """
        Validate scope is within Cursor's allowed range.

        Args:
            scope: Single scope string or list of scope strings

        Raises:
            CursorScopeViolationError: If scope is not allowed
        """
        scopes = [scope] if isinstance(scope, str) else scope

        for s in scopes:
            if s not in self.ALLOWED_SCOPES:
                logger.error(
                    "Cursor scope violation",
                    requested_scope=s,
                    allowed_scopes=list(self.ALLOWED_SCOPES),
                )
                raise CursorScopeViolationError(f"Cursor cannot access scope '{s}'. Allowed: {self.ALLOWED_SCOPES}")

    def _build_cursor_governance_context(self):
        """Build governance context for Cursor operations."""
        return build_governance_context(
            caller_id="cursor_gateway",
            role="developer",
            tenant_id="cursor",
            org_id="l9",
            project_ids=["cursor"],
        )

    @must_stay_async("callers use await")
    async def write_decision(
        self,
        state: Any,  # CursorAgentState
    ) -> UUID:
        """
        Write a decision packet to memory substrate.

        Args:
            state: CursorAgentState with decision information

        Returns:
            Packet ID of written envelope
        """
        logger.info("Writing decision to memory", thread_id=state.thread_id)

        # Build payload from state
        payload = {
            "task": state.task,
            "current_file": state.current_file,
            "selected_code": state.selected_code,
            "decision": state.decisions[-1] if state.decisions else {},
            "reasoning_trace": [
                block.model_dump() if hasattr(block, "model_dump") else block for block in state.reasoning_trace
            ],
            "task_status": state.task_status,
        }

        # Build PacketEnvelopeIn
        packet_in = PacketEnvelopeIn(
            packet_type="cursor_decision",
            payload=payload,
            thread_id=UUID(state.thread_id) if state.thread_id else None,
            tags=["cursor", "decision"],
            metadata=None,  # Will use defaults
        )

        # Write via substrate service with governance context
        ctx = self._build_cursor_governance_context()
        async with governance_context(ctx):
            result = await self._substrate_service.write_packet(packet_in)

        if result.status != "ok":
            raise RuntimeError(f"Failed to write decision: {result.error_message}")

        logger.info("Decision written", packet_id=result.packet_id)
        return result.packet_id

    @must_stay_async("callers use await")
    async def write_error(
        self,
        state: Any,  # CursorAgentState
    ) -> UUID:
        """
        Write an error packet to memory substrate.

        Args:
            state: CursorAgentState with error information

        Returns:
            Packet ID of written envelope
        """
        logger.info("Writing error to memory", thread_id=state.thread_id)

        # Build payload from state errors
        last_error = state.errors[-1] if state.errors else {}
        payload = {
            "error_type": last_error.get("type", "unknown"),
            "error_message": last_error.get("error", ""),
            "task": state.task,
            "current_file": state.current_file,
            "recovery_suggestions": state.recovery_suggestions,
            "context": {
                "thread_id": state.thread_id,
                "task_status": state.task_status,
            },
        }

        # Build PacketEnvelopeIn
        packet_in = PacketEnvelopeIn(
            packet_type="cursor_error",
            payload=payload,
            thread_id=UUID(state.thread_id) if state.thread_id else None,
            tags=["cursor", "error"],
            metadata=None,
        )

        # Write via substrate service with governance context
        ctx = self._build_cursor_governance_context()
        async with governance_context(ctx):
            result = await self._substrate_service.write_packet(packet_in)

        if result.status != "ok":
            raise RuntimeError(f"Failed to write error: {result.error_message}")

        logger.info("Error written", packet_id=result.packet_id)
        return result.packet_id

    @must_stay_async("callers use await")
    async def search_memory(
        self,
        query: str,
        scope: list[str],
        project_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search memory substrate using semantic search.

        LGRAPH-007: Implemented via MemorySubstrateService.semantic_search()

        Args:
            query: Search query string
            scope: List of scopes to search (must be subset of ALLOWED_SCOPES)
            project_id: Project identifier
            limit: Maximum number of results

        Returns:
            List of search hits, each containing packet_id, similarity_score, metadata

        Raises:
            CursorScopeViolationError: If scope contains disallowed values
        """
        logger.info("Searching memory", query=query[:50], scope=scope, limit=limit)

        # Validate scope
        self._validate_scope(scope)

        try:
            # Build semantic search request
            request = SemanticSearchRequest(
                query=query,
                top_k=limit,
                agent_id=None,  # Search across all agents
            )

            # Execute semantic search with governance context
            ctx = self._build_cursor_governance_context()
            async with governance_context(ctx):
                result = await self._substrate_service.semantic_search(request)

            # Transform hits to expected format
            hits = []
            for hit in result.hits:
                hits.append(
                    {
                        "packet_id": str(hit.embedding_id),
                        "similarity_score": hit.score,
                        "metadata": hit.payload,
                        "scope": hit.payload.get("scope", "unknown"),
                    }
                )

            # Filter by allowed scopes
            filtered_hits = [h for h in hits if h.get("scope", "developer") in self.ALLOWED_SCOPES]

            logger.info(
                "Memory search completed",
                total_hits=len(result.hits),
                filtered_hits=len(filtered_hits),
            )
            return filtered_hits

        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            # Return empty list on error (graceful degradation)
            return []

    @must_stay_async("callers use await")
    async def write_checkpoint(
        self,
        thread_id: str,
        state: Any,  # CursorAgentState
    ) -> UUID:
        """
        Write a checkpoint packet to memory substrate (dual checkpoint strategy).

        Args:
            thread_id: Thread identifier
            state: CursorAgentState to checkpoint

        Returns:
            Packet ID of written checkpoint envelope
        """
        logger.info("Writing checkpoint to memory", thread_id=thread_id)

        # Serialize state (trim oversized fields if necessary)
        state_dict = state.model_dump() if hasattr(state, "model_dump") else {}

        # Trim selected_code if too long
        if state_dict.get("selected_code") and len(state_dict["selected_code"]) > 10000:
            state_dict["selected_code"] = state_dict["selected_code"][:10000] + "... [truncated]"

        payload = {
            "thread_id": thread_id,
            "state": state_dict,
            "checkpoint_type": "cursor_langgraph",
        }

        # Build PacketEnvelopeIn
        packet_in = PacketEnvelopeIn(
            packet_type="cursor_checkpoint",
            payload=payload,
            thread_id=UUID(thread_id) if thread_id else None,
            tags=["cursor", "checkpoint"],
            metadata=None,
        )

        # Write via substrate service with governance context
        ctx = self._build_cursor_governance_context()
        async with governance_context(ctx):
            result = await self._substrate_service.write_packet(packet_in)

        if result.status != "ok":
            raise RuntimeError(f"Failed to write checkpoint: {result.error_message}")

        logger.info("Checkpoint written", packet_id=result.packet_id)
        return result.packet_id

    @must_stay_async("future await planned")
    async def load_checkpoint(
        self,
        thread_id: str,
    ) -> Any | None:  # Optional[CursorAgentState]
        """
        Load checkpoint from memory substrate (fallback for dual checkpoint).

        LGRAPH-006: Implemented via MemorySubstrateService.search_packets_by_thread()

        Args:
            thread_id: Thread identifier

        Returns:
            CursorAgentState if found, None otherwise
        """
        logger.info("Loading checkpoint from memory", thread_id=thread_id)

        try:
            # Search for checkpoint packets by thread_id
            ctx = self._build_cursor_governance_context()
            async with governance_context(ctx):
                packets = await self._substrate_service.search_packets_by_thread(
                    thread_id=thread_id,
                    packet_type="cursor_checkpoint",
                    limit=1,  # Get most recent
                )

            if not packets:
                logger.info("No checkpoint found for thread", thread_id=thread_id)
                return None

            # Get most recent checkpoint
            checkpoint_packet = packets[0]
            payload = checkpoint_packet.get("payload", {})
            state_dict = payload.get("state", {})

            if not state_dict:
                logger.warning("Checkpoint packet has no state", thread_id=thread_id)
                return None

            # Import here to avoid circular dependency
            from agents.cursor.integrations.cursor_langgraph import CursorAgentState

            # Reconstruct CursorAgentState
            state = CursorAgentState(**state_dict)
            logger.info("Checkpoint loaded from memory", thread_id=thread_id)
            return state

        except Exception as e:
            logger.error("Failed to load checkpoint", error=str(e), thread_id=thread_id)
            return None


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-023",
    "governance_level": "high",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [
        "agents.cursor.integrations.cursor_langgraph",
        "core.decorators",
        "core.schemas",
        "memory.governance_gate",
        "memory.substrate_service",
    ],
    "tags": [
        "async",
        "error-handling",
        "exception",
        "intelligence",
        "logging",
        "messaging",
        "tracing",
    ],
    "keywords": [
        "checkpoint",
        "cursor",
        "decision",
        "gateway",
        "global",
        "implemented",
        "lgraph",
        "load",
    ],
    "business_value": "Provides cursor gateway components including CursorScopeViolationError, CursorMemoryGateway",
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
