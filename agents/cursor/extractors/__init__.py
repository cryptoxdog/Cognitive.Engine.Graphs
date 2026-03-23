"""
L9 Cursor Extractors

Extractors for processing chat history and artifacts.
"""

from agents.cursor.extractors.base_extractor import BaseExtractor
from agents.cursor.extractors.cursor_action_extractor import CursorActionExtractor

__all__ = ["BaseExtractor", "CursorActionExtractor"]

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Extractors",
    "module_version": "1.0.1",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-11T18:13:39Z",
    "updated_at": "2026-02-02T23:30:00Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "__init__",
    "type": "utility",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": [],
        "imported_by": [],
    },
}
# ============================================================================
# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-035",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": ["agent-execution", "intelligence", "utility"],
    "keywords": [],
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
