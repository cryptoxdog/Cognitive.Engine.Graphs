# agents/cursor/cursor_session_hooks.py
"""
Hooks into Cursor session start/action/end.
Maintains working memory without modifying AgentExecutor.

Async-compatible for L9 architecture.
"""

from __future__ import annotations

from core.decorators import must_stay_async

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Session Hooks",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-28T22:45:42Z",
    "updated_at": "2026-02-02T10:35:00Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "cursor_session_hooks",
    "type": "service",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": ["working_memory"],
        "imported_by": [],
    },
}
# ============================================================================

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memory_cache.working_memory_service import WorkingMemoryService


class CursorSessionHooks:
    """
    Non-invasive session lifecycle management for Cursor.

    Invariant: all Cursor tool calls flow through on_action()
    """

    def __init__(
        self,
        wmc: WorkingMemoryService,
        memory_service,  # from L9 memory substrate
        logger=None,
    ):
        """
        Initializes CursorSessionHooks for non-invasive lifecycle management of Cursor sessions, maintaining session state without modifying AgentExecutor.

        Args:
            wmc: WorkingMemoryService instance managing session memory.
            memory_service: Underlying memory substrate for session data.
            logger: Optional logger for debugging and tracing session events; defaults to no-op.
        """
        self.wmc = wmc
        self.memory = memory_service
        self.logger = logger or self._noop_logger

    @staticmethod
    def _noop_logger(*args, **kwargs):
        """
        Performs no operation; used as a placeholder logger within Cursor session hooks.

        Args:
            *args: Positional arguments passed to the logger.
            **kwargs: Keyword arguments passed to the logger.
        """

    # === SESSION LIFECYCLE ===

    async def on_session_start(
        self,
        repo_id: str,
        branch: str,
    ) -> dict[str, Any] | None:
        """
        Called: before context assembly in Cursor.run()
        Effect: hydrate cross-window state
        Returns: cache snapshot (to be injected) or None
        """
        snapshot = await self.wmc.hydrate(repo_id, branch)
        if snapshot:
            self.logger(f"[CursorWMC] resuming session: {snapshot.intent}")
            return {
                "intent": snapshot.intent,
                "files_context": snapshot.files_touched[-20:],  # recent 20
                "recent_decisions": snapshot.recent_decisions[-5:],  # last 5
                "errors_to_avoid": snapshot.recent_errors[-3:],  # last 3
                "open_hypotheses": snapshot.open_hypotheses,
                "cached_at": snapshot.updated_at,
            }
        self.logger("[CursorWMC] cold start")
        return None

    @must_stay_async("callers use await")
    async def on_action(
        self,
        repo_id: str,
        branch: str,
        tool_id: str,
        args: dict[str, Any],
        success: bool = True,
        error: str | None = None,
        repo_state_hash: str | None = None,
    ) -> None:
        """
        Called: after each Cursor tool execution
        Effect: record action in working memory

        This is the hot path — keep it fast.
        """
        action_record = {
            "type": tool_id,
            "args_summary": self._summarize_args(args),
            "success": success,
        }

        if error:
            action_record["error"] = error

        # Extract files touched (tool-specific)
        files_touched = self._extract_files_from_action(tool_id, args)

        # Update WMC incrementally
        await self.wmc.update(
            repo_id,
            branch,
            action=action_record,
            files_touched=files_touched,
            error={"tool": tool_id, "msg": error} if error else None,
            repo_state_hash=repo_state_hash,
        )

        self.logger(f"[CursorWMC] recorded {tool_id} action")

    async def on_session_end(
        self,
        repo_id: str,
        branch: str,
        promote: bool = False,
    ) -> None:
        """
        Called: after Cursor task completion or explicit end

        Args:
            promote: if True, escalate high-confidence items to long-term memory
                    if False, let cache expire naturally (default, safer)

        Effect: if promote=True, trigger promotion flow; otherwise do nothing
        """
        if promote:
            snapshot = await self.wmc.hydrate(repo_id, branch)
            if snapshot:
                await self._promote_to_memory(repo_id, snapshot)

        # Don't clear; let TTL do the work
        self.logger("[CursorWMC] session ended (cache expires naturally)")

    # === INTERNALS ===

    @staticmethod
    def _summarize_args(args: dict[str, Any], max_len: int = 200) -> dict[str, Any]:
        """Shrink args for storage (no full payloads)."""
        summary = {}
        for k, v in args.items():
            if isinstance(v, str):
                summary[k] = v[:max_len]
            elif isinstance(v, (int, float, bool)):
                summary[k] = v
            elif isinstance(v, (list, dict)):
                summary[k] = f"<{type(v).__name__} len={len(v)}>"
            else:
                summary[k] = str(type(v).__name__)
        return summary

    @staticmethod
    def _extract_files_from_action(tool_id: str, args: dict[str, Any]) -> list:
        """
        Extract file paths from tool args (tool-specific).
        Extend this for new tools.
        """
        files = []

        if tool_id in ["read_file", "get_file_contents"] or tool_id in [
            "write_file",
            "create_or_update_file",
        ]:
            if "path" in args:
                files.append(args["path"])

        elif tool_id == "search_code":
            # Search tools don't directly touch files, but note the query scope
            pass

        elif tool_id in ["list_files", "get_directory_contents"]:
            if "path" in args:
                files.append(args["path"])

        return files

    async def _promote_to_memory(self, repo_id: str, snapshot) -> None:
        """
        Escalate working memory to long-term memory.
        Only called if user confirms or test passed.

        THIS IS STRICT: promotion requires explicit signal.
        """
        # Write consolidated decision as FACT
        if snapshot.intent:
            await self.memory.write(
                kind="FACT",
                content={
                    "type": "cursor_intent",
                    "repo_id": repo_id,
                    "intent": snapshot.intent,
                    "files_involved": snapshot.files_touched[:10],
                    "confidence": "user_confirmed",
                },
            )

        # Write recent errors as FAILURES (so they're not repeated)
        for error in snapshot.recent_errors[-2:]:
            await self.memory.write(
                kind="FAILURE",
                content={
                    "repo_id": repo_id,
                    "error": error,
                    "rule": "DO_NOT_REPEAT",
                },
            )

        self.logger("[CursorWMC] promoted high-confidence items to long-term memory")


# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-009",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": [
        "agent-execution",
        "async",
        "caching",
        "debugging",
        "event-driven",
        "intelligence",
        "security",
        "service",
        "testing",
    ],
    "keywords": ["action", "cursor", "end", "hooks", "session", "start"],
    "business_value": "Implements CursorSessionHooks for cursor session hooks functionality",
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
