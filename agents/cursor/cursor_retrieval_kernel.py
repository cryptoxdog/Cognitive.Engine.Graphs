# agents/cursor/cursor_retrieval_kernel.py
"""
Enforces: Check working memory → long-term memory → repo (no skipping)
This is the core of eliminating grepping.

Async-compatible for L9 architecture.
"""

from __future__ import annotations

from core.decorators import must_stay_async

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Retrieval Kernel",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-28T22:45:42Z",
    "updated_at": "2026-02-02T10:35:00Z",
    "layer": "intelligence",
    "domain": "data_models",
    "module_name": "cursor_retrieval_kernel",
    "type": "enum",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": ["working_memory", "semantic_memory"],
        "imported_by": [],
    },
}
# ============================================================================

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memory_cache.working_memory_service import WorkingMemoryService


class RetrievalSource(StrEnum):
    """
    Decision engine managing cursor context retrieval order, ensuring cache and memory checks precede repository scans for efficient knowledge access.

    Args:
        retrieval_source (RetrievalSource): The current source from which to retrieve cursor context.
        cache (dict): In-memory cache of retrieved data.
        memory (dict): Long-term memory storage for cursor contexts.
        repo (Repository): Repository interface for scanning external sources.

    Returns:
        str: The selected retrieval source based on current cache and memory state.

    Raises:
        ValueError: If an invalid retrieval source is provided.
    """

    WORKING_MEMORY = "working_memory"
    LONG_TERM_MEMORY = "long_term_memory"
    REPO_SCAN = "repo_scan"


class CursorRetrievalKernel:
    """
    Decision engine for Cursor context retrieval.

    Invariant: NEVER repo-scan before checking cache + memory.
    """

    def __init__(
        self,
        wmc: WorkingMemoryService,
        memory_service,
        logger=None,
    ):
        """Initialize the retrieval kernel.

        Args:
            wmc: Working memory cache service.
            memory_service: Long-term memory service for semantic search.
            logger: Optional logging function.
        """
        self.wmc = wmc
        self.memory = memory_service
        self.logger = logger or self._noop_logger

    @staticmethod
    def _noop_logger(*args, **kwargs):
        """No-op logger for when no logger is provided."""

    @must_stay_async("callers use await")
    async def retrieve_context(
        self,
        repo_id: str,
        branch: str,
        query: str,
        context_type: str | None = None,  # "file", "function", "pattern"
    ) -> tuple[RetrievalSource, dict[str, Any]]:
        """
        Three-tier retrieval: working memory → long-term → repo.

        Args:
            repo_id, branch: scope
            query: "where is X", "how do we handle Y", etc
            context_type: hint for ranking (optional)

        Returns:
            (source, data) tuple indicating where answer came from

        Invariant: NEVER returns (REPO_SCAN, None). If repo_scan needed,
                   data field contains instruction to scan (not results).
        """

        # TIER 1: Working Memory (same session)
        wmc_context = await self._check_working_memory(repo_id, branch, query)
        if wmc_context:
            self.logger(f"[CursorKernel] working memory HIT: {query}")
            return (RetrievalSource.WORKING_MEMORY, wmc_context)

        # TIER 2: Long-Term Memory (semantic + hybrid search)
        ltm_context = await self._check_long_term_memory(query, context_type)
        if ltm_context:
            self.logger(f"[CursorKernel] long-term memory HIT: {query}")
            return (RetrievalSource.LONG_TERM_MEMORY, ltm_context)

        # TIER 3: Repo Scan (controlled, logged)
        self.logger(f"[CursorKernel] falling back to repo scan: {query}")
        return (RetrievalSource.REPO_SCAN, {"instruction": "scan_repo", "query": query})

    async def _check_working_memory(
        self,
        repo_id: str,
        branch: str,
        query: str,
    ) -> dict[str, Any] | None:
        """
        Check WMC for relevant context.
        Fast, exact match only.
        """
        snapshot = await self.wmc.hydrate(repo_id, branch)
        if not snapshot:
            return None

        # Simple heuristics: does query match recent context?
        query_lower = query.lower()

        # Check files touched
        for f in snapshot.files_touched:
            if query_lower in f.lower():
                return {
                    "source": "working_memory",
                    "type": "file_context",
                    "files": snapshot.files_touched[-10:],
                    "recent_decisions": snapshot.recent_decisions[-3:],
                }

        # Check intent
        if snapshot.intent and query_lower in snapshot.intent.lower():
            return {
                "source": "working_memory",
                "type": "intent_context",
                "intent": snapshot.intent,
                "hypotheses": snapshot.open_hypotheses,
            }

        return None

    async def _check_long_term_memory(
        self,
        query: str,
        context_type: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Query long-term memory (semantic search).
        """
        try:
            results = await self.memory.search(
                query=query,
                top_k=3,
                kind=None,  # don't filter by kind; let search decide
            )
            if results:
                return {
                    "source": "long_term_memory",
                    "type": "semantic_match",
                    "results": results,
                }
        except Exception as e:
            self.logger(f"[CursorKernel] long-term memory search failed: {e}")

        return None

    def mark_repo_scan_necessary(
        self,
        query: str,
        reason: str = "no_cache_hit",
    ) -> None:
        """
        Log when repo scan is unavoidable (for metrics/audit).
        """
        self.logger(f"[CursorKernel] repo scan required: {reason} (query: {query})")


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-010",
    "governance_level": "high",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": ["async", "caching", "data-models", "enum", "intelligence", "metrics"],
    "keywords": [
        "cursor",
        "kernel",
        "mark",
        "necessary",
        "repo",
        "retrieval",
        "retrieve",
        "scan",
    ],
    "business_value": "This is the core of eliminating grepping. Async-compatible for L9 architecture.",
    "last_modified": "2026-01-31T22:21:54Z",
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
