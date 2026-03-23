"""
L9 Cursor Agent Integration

Cursor-specific modules for IDE integration, memory management, and LangGraph orchestration.
All cursor-related code is consolidated here for easier maintenance and clear separation.

Includes:
- CursorMemoryKernel: Session state, lessons, TODOs
- CursorClient: API client for Cursor
- GMP Meta-Learning: Execution tracking, heuristics, autonomy graduation
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "  Init  ",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-11T18:13:39Z",
    "updated_at": "2026-01-31T22:21:54Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "__init__",
    "type": "client",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": [],
        "imported_by": [],
    },
}
# ============================================================================

from agents.cursor.cursor_client import CursorClient
from agents.cursor.cursor_memory_kernel import (
    CursorMemoryKernel,
    Lesson,
    SessionState,
    TodoItem,
    activate_session,
    create_cursor_memory_kernel,
    get_active_kernel,
)

# GMP v2.0 Meta-Learning (Cursor-specific)
from agents.cursor.gmp_meta_learning import (
    AutonomyController,
    AutonomyGraduationMetrics,
    AutonomyLevel,
    GMPExecutionResult,
    GMPMetaLearningEngine,
    LearnedHeuristic,
)

__all__ = [
    "AutonomyController",
    "AutonomyGraduationMetrics",
    "AutonomyLevel",
    # Client
    "CursorClient",
    # Kernel
    "CursorMemoryKernel",
    "GMPExecutionResult",
    # GMP Meta-Learning
    "GMPMetaLearningEngine",
    "LearnedHeuristic",
    "Lesson",
    "SessionState",
    "TodoItem",
    "activate_session",
    "create_cursor_memory_kernel",
    "get_active_kernel",
]
# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-011",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [
        "agents.cursor.cursor_client",
        "agents.cursor.cursor_memory_kernel",
        "agents.cursor.gmp_meta_learning",
    ],
    "tags": ["agent-execution", "api", "client", "intelligence", "metrics"],
    "keywords": ["agent", "cursor", "integration", "memory", "state"],
    "business_value": "Utility module for   init  ",
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
