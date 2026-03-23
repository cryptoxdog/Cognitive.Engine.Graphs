# README Generation Request for: Cursor Module

## SYSTEM CONTEXT

You are generating a **gold-standard README** for the `agents/cursor` module in L9 Secure AI OS.

### Core Principles
1. **Documentation as Contract** — README specifies scope, APIs, invariants, AI rules
2. **Zero Hallucination** — Use ONLY the facts provided below, do NOT invent
3. **Production-Grade** — Complete, deployable, no placeholders

---

## EXTRACTED FACTS (GROUND TRUTH)

**Path:** `agents/cursor`
**Files:** 23 Python files
**Classes:** 30
**Functions:** 65
**Pydantic Models:** 9
**API Routes:** 0

### File List
```
agents/cursor/GMP-v2.0-Perplex-Py-Scripts/script.py
agents/cursor/GMP-v2.0-Perplex-Py-Scripts/script_1.py
agents/cursor/GMP-v2.0-Perplex-Py-Scripts/script_2.py
agents/cursor/GMP-v2.0-Perplex-Py-Scripts/script_3.py
agents/cursor/GMP-v2.0-Perplex-Py-Scripts/script_4.py
agents/cursor/__init__.py
agents/cursor/cursor_client.py
agents/cursor/cursor_memory_client.py
agents/cursor/cursor_memory_kernel.py
agents/cursor/cursor_neo4j_query.py
agents/cursor/cursor_retrieval_kernel.py
agents/cursor/cursor_session_hooks.py
agents/cursor/extractors/__init__.py
agents/cursor/extractors/base_extractor.py
agents/cursor/extractors/cursor_action_extractor.py
agents/cursor/gmp_meta_learning.py
agents/cursor/ingest_lessons.py
agents/cursor/integrations/__init__.py
agents/cursor/integrations/cursor_executor.py
agents/cursor/integrations/cursor_gateway.py
agents/cursor/integrations/cursor_langgraph.py
agents/cursor/scripts/__init__.py
agents/cursor/scripts/cursor_check_mistakes.py
```

### Classes (with methods and fields)
#### `CursorClient` (agents/cursor/cursor_client.py:36-113)
**Docstring:** Client for Cursor remote API.

**Methods:**
- `__init__(self: Any, host: str, port: int, timeout: int)`
- `_request(self: Any, endpoint: str, method: str, data: dict | None) -> dict[str, Any]`
- `send_code(self: Any, code: str) -> dict[str, Any]`
- `send_command(self: Any, command: str) -> dict[str, Any]`
- `health_check(self: Any) -> dict[str, Any]`

#### `CursorSessionHooks` (agents/cursor/cursor_session_hooks.py:40-239)
**Docstring:** Non-invasive session lifecycle management for Cursor.

**Methods:**
- `__init__(self: Any, wmc: WorkingMemoryService, memory_service: Any, logger: Any)`
- `_noop_logger()`
- `async on_session_start(self: Any, repo_id: str, branch: str) -> dict[str, Any] | None`
- `async on_action(self: Any, repo_id: str, branch: str, tool_id: str, args: dict[str, Any]) -> None`
- `async on_session_end(self: Any, repo_id: str, branch: str, promote: bool) -> None`
- `_summarize_args(args: dict[str, Any], max_len: int) -> dict[str, Any]`
- `_extract_files_from_action(tool_id: str, args: dict[str, Any]) -> list`
- `async _promote_to_memory(self: Any, repo_id: str, snapshot: Any) -> None`

#### `RetrievalSource` (agents/cursor/cursor_retrieval_kernel.py:41-60)
**Bases:** `str`, `Enum`
**Docstring:** Decision engine managing cursor context retrieval order, ensuring cache and memory checks precede repository scans for efficient knowledge access.

#### `CursorRetrievalKernel` (agents/cursor/cursor_retrieval_kernel.py:63-202)
**Docstring:** Decision engine for Cursor context retrieval.

**Methods:**
- `__init__(self: Any, wmc: WorkingMemoryService, memory_service: Any, logger: Any)`
- `_noop_logger()`
- `async retrieve_context(self: Any, repo_id: str, branch: str, query: str, context_type: str | None) -> tuple[RetrievalSource, dict[str, Any]]`
- `async _check_working_memory(self: Any, repo_id: str, branch: str, query: str) -> dict[str, Any] | None`
- `async _check_long_term_memory(self: Any, query: str, context_type: str | None) -> dict[str, Any] | None`
- `mark_repo_scan_necessary(self: Any, query: str, reason: str) -> None`

#### `AutonomyLevel` (agents/cursor/gmp_meta_learning.py:64-70)
**Bases:** `str`, `Enum`
**Docstring:** Graduated autonomy levels in GMP v2.0.

#### `GMPExecutionResult` (agents/cursor/gmp_meta_learning.py:73-104)
**Bases:** `BaseModel`
**Docstring:** Results from a completed GMP execution.

**Fields:**
- `gmp_id: str = Field(...)`
- `task_type: str = Field(...)`
- `todo_count: int = Field(...)`
- `execution_minutes: float = Field(...)`
- `error_count: int = Field(...)`
- `error_types: list[str] = Field(...)`
- `files_modified: list[str] = Field(...)`
- `lines_changed: int = Field(...)`
- `final_confidence: float = Field(...)`
- `audit_result: str = Field(...)`
- `created_at: datetime = Field(...)`
- `l9_kernel_versions: dict[str, str] = Field(...)`
- `feature_flags_enabled: list[str] = Field(...)`

#### `LearnedHeuristic` (agents/cursor/gmp_meta_learning.py:107-130)
**Bases:** `BaseModel`
**Docstring:** A heuristic pattern learned from prior executions.

**Fields:**
- `heuristic_id: str = Field(...)`
- `pattern_text: str = Field(...)`
- `condition: str = Field(...)`
- `recommendation: str = Field(...)`
- `confidence: float = Field(...)`
- `supporting_gmp_ids: list[str] = Field(...)`
- `impact_estimate: str = Field(...)`
- `generated_date: datetime = Field(...)`
- `active: bool = Field(...)`

**Methods:**
- `__hash__(self: Any)`

#### `AutonomyGraduationMetrics` (agents/cursor/gmp_meta_learning.py:133-154)
**Bases:** `BaseModel`
**Docstring:** Tracks metrics for autonomy level graduation.

**Fields:**
- `current_level: AutonomyLevel = Field(...)`
- `perfect_executions_l2: int = Field(...)`
- `consistency_score_l3: float = Field(...)`
- `safety_audit_passed_l4: bool = Field(...)`
- `l2_to_l3_ready: bool = Field(...)`
- `l3_to_l4_ready: bool = Field(...)`
- `l4_to_l5_ready: bool = Field(...)`
- `last_updated: datetime = Field(...)`

#### `GMPExecutionHistoryDB` (agents/cursor/gmp_meta_learning.py:164-189)
**Bases:** `Base`
**Docstring:** Stores execution history in PostgreSQL.

#### `LearnedHeuristicDB` (agents/cursor/gmp_meta_learning.py:192-208)
**Bases:** `Base`
**Docstring:** Stores learned heuristics in PostgreSQL.

#### `AutonomyMetricsDB` (agents/cursor/gmp_meta_learning.py:211-226)
**Bases:** `Base`
**Docstring:** Stores autonomy graduation metrics in PostgreSQL.

#### `GMPMetaLearningEngine` (agents/cursor/gmp_meta_learning.py:234-626)
**Docstring:** Processes GMP execution history to extract patterns and generate heuristics.

**Methods:**
- `__init__(self: Any, database_url: str)`
- `async create_tables(self: Any) -> None`
- `async log_execution(self: Any, result: GMPExecutionResult) -> bool`
- `async analyze_execution_patterns(self: Any) -> dict[str, Any]`
- `async generate_heuristics(self: Any) -> list[LearnedHeuristic]`
- `async get_active_heuristics(self: Any) -> list[LearnedHeuristic]`
- `async update_autonomy_metrics(self: Any, execution: GMPExecutionResult) -> AutonomyGraduationMetrics`
- `_calculate_correlation(x: list[float], y: list[float]) -> float`

#### `AutonomyController` (agents/cursor/gmp_meta_learning.py:634-796)
**Docstring:** Manages autonomy level graduation and feature flag enforcement.

**Methods:**
- `__init__(self: Any, learning_engine: GMPMetaLearningEngine)`
- `async get_current_autonomy_level(self: Any) -> AutonomyLevel`
- `async assert_capability(self: Any, feature: str) -> bool`
- `async can_graduate_to_next_level(self: Any) -> tuple[bool, str | None]`
- `async graduate_to_next_level(self: Any) -> tuple[bool, str]`

#### `Lesson` (agents/cursor/cursor_memory_kernel.py:98-103)
**Decorators:** `dataclass`
**Docstring:** A lesson loaded from memory.

**Fields:**
- `title: str`
- `severity: str`
- `content: str`

#### `TodoItem` (agents/cursor/cursor_memory_kernel.py:107-113)
**Decorators:** `dataclass`
**Docstring:** A tracked TODO item.

**Fields:**
- `id: str`
- `content: str`
- `status: str`
- `milestone: str | None = None`

*... and 15 more classes*

### Pydantic/Dataclass Models
#### `GMPExecutionResult` (agents/cursor/gmp_meta_learning.py:73-104)
**Bases:** `BaseModel`
**Docstring:** Results from a completed GMP execution.

**Fields:**
- `gmp_id: str = Field(...)`
- `task_type: str = Field(...)`
- `todo_count: int = Field(...)`
- `execution_minutes: float = Field(...)`
- `error_count: int = Field(...)`
- `error_types: list[str] = Field(...)`
- `files_modified: list[str] = Field(...)`
- `lines_changed: int = Field(...)`
- `final_confidence: float = Field(...)`
- `audit_result: str = Field(...)`
- `created_at: datetime = Field(...)`
- `l9_kernel_versions: dict[str, str] = Field(...)`
- `feature_flags_enabled: list[str] = Field(...)`

#### `LearnedHeuristic` (agents/cursor/gmp_meta_learning.py:107-130)
**Bases:** `BaseModel`
**Docstring:** A heuristic pattern learned from prior executions.

**Fields:**
- `heuristic_id: str = Field(...)`
- `pattern_text: str = Field(...)`
- `condition: str = Field(...)`
- `recommendation: str = Field(...)`
- `confidence: float = Field(...)`
- `supporting_gmp_ids: list[str] = Field(...)`
- `impact_estimate: str = Field(...)`
- `generated_date: datetime = Field(...)`
- `active: bool = Field(...)`

**Methods:**
- `__hash__(self: Any)`

#### `AutonomyGraduationMetrics` (agents/cursor/gmp_meta_learning.py:133-154)
**Bases:** `BaseModel`
**Docstring:** Tracks metrics for autonomy level graduation.

**Fields:**
- `current_level: AutonomyLevel = Field(...)`
- `perfect_executions_l2: int = Field(...)`
- `consistency_score_l3: float = Field(...)`
- `safety_audit_passed_l4: bool = Field(...)`
- `l2_to_l3_ready: bool = Field(...)`
- `l3_to_l4_ready: bool = Field(...)`
- `l4_to_l5_ready: bool = Field(...)`
- `last_updated: datetime = Field(...)`

#### `Lesson` (agents/cursor/cursor_memory_kernel.py:98-103)
**Decorators:** `dataclass`
**Docstring:** A lesson loaded from memory.

**Fields:**
- `title: str`
- `severity: str`
- `content: str`

#### `TodoItem` (agents/cursor/cursor_memory_kernel.py:107-113)
**Decorators:** `dataclass`
**Docstring:** A tracked TODO item.

**Fields:**
- `id: str`
- `content: str`
- `status: str`
- `milestone: str | None = None`

#### `SessionState` (agents/cursor/cursor_memory_kernel.py:117-125)
**Decorators:** `dataclass`
**Docstring:** Current session state from memory.

**Fields:**
- `kernel_id: str`
- `session_id: str`
- `lessons: list[Lesson] = field(...)`
- `todos: list[TodoItem] = field(...)`
- `prompt_count: int = 0`
- `activated_at: datetime | None = None`

#### `CursorTaskSpec` (agents/cursor/integrations/cursor_executor.py:56-65)
**Bases:** `BaseModel`
**Docstring:** Task specification for Cursor executor.

**Fields:**
- `task: str = Field(...)`
- `project_id: str = Field(...)`
- `initial_state: CursorAgentState | None = Field(...)`
- `entry_file: str | None = Field(...)`
- `selection: str | None = Field(...)`

#### `CursorResult` (agents/cursor/integrations/cursor_executor.py:68-81)
**Bases:** `BaseModel`
**Docstring:** Result of Cursor task execution.

**Fields:**
- `thread_id: str = Field(...)`
- `final_state: CursorAgentState = Field(...)`
- `decisions: list[dict[str, Any]] = Field(...)`
- `errors: list[dict[str, Any]] = Field(...)`
- `reasoning_trace: list[dict[str, Any]] = Field(...)`

#### `CursorAgentState` (agents/cursor/integrations/cursor_langgraph.py:59-119)
**Bases:** `BaseModel`
**Docstring:** LangGraph state model for Cursor agent execution.

**Fields:**
- `thread_id: str | None = Field(...)`
- `task_id: str | None = Field(...)`
- `messages: list[dict[str, Any]] = Field(...)`
- `task: str | None = Field(...)`
- `task_status: Literal['pending', 'running', 'completed', 'failed'] = Field(...)`
- `current_file: str | None = Field(...)`
- `selected_code: str | None = Field(...)`
- `project_id: str | None = Field(...)`
- `reasoning_trace: list[dict[str, Any]] = Field(...)`
- `decisions: list[dict[str, Any]] = Field(...)`
- `tool_results: list[dict[str, Any]] = Field(...)`
- `search_hits: list[dict[str, Any]] = Field(...)`
- `last_checkpoint_id: str | None = Field(...)`
- `last_packet_id: UUID | None = Field(...)`
- `approval_status: str | None = Field(...)`
- `approval_id: str | None = Field(...)`
- `errors: list[dict[str, Any]] = Field(...)`
- `recovery_suggestions: list[str] = Field(...)`

### API Routes
*No API routes found*

### Top-Level Functions
#### `main` (agents/cursor/gmp_meta_learning.py:804)
**Signature:** `async def main()`
**Docstring:** Example demonstrating GMP v2.0 learning engine (async).

#### `parse_lessons` (agents/cursor/ingest_lessons.py:77)
**Signature:** `def parse_lessons(path: Path) -> list[dict]`
**Docstring:** Parse repeated-mistakes.md into structured lesson dicts.

#### `_classify_severity` (agents/cursor/ingest_lessons.py:191)
**Signature:** `def _classify_severity(marker: str) -> str`

#### `write_lesson_to_mcp` (agents/cursor/ingest_lessons.py:209)
**Signature:** `def write_lesson_to_mcp(lesson: dict) -> dict`
**Docstring:** Write a single lesson to MCP memory via save_memory tool.

#### `main` (agents/cursor/ingest_lessons.py:261)
**Signature:** `def main() -> None`

#### `get_daily_session_id` (agents/cursor/cursor_memory_client.py:131)
**Signature:** `def get_daily_session_id() -> str`
**Docstring:** Generate deterministic session UUID based on current date.

#### `compute_content_hash` (agents/cursor/cursor_memory_client.py:143)
**Signature:** `def compute_content_hash(payload: dict) -> str`
**Docstring:** Compute SHA-256 content hash for PacketEnvelope v2.0 integrity.

#### `mcp_call_tool` (agents/cursor/cursor_memory_client.py:194)
**Signature:** `def mcp_call_tool(tool_name: str, arguments: dict) -> dict`
**Docstring:** Call MCP tool via /mcp/call endpoint.

#### `api_request` (agents/cursor/cursor_memory_client.py:236)
**Signature:** `def api_request(method: str, path: str, data: dict | None) -> dict`
**Docstring:** Direct HTTP API request (FALLBACK ONLY).

#### `cmd_stats` (agents/cursor/cursor_memory_client.py:276)
**Signature:** `def cmd_stats()`
**Docstring:** Get memory stats via MCP.

#### `cmd_health` (agents/cursor/cursor_memory_client.py:288)
**Signature:** `def cmd_health()`
**Docstring:** Check MCP memory health (PRIMARY) and API health (FALLBACK).

#### `cmd_search` (agents/cursor/cursor_memory_client.py:368)
**Signature:** `def cmd_search(query: str, limit: int, min_confidence: float, sort_by: str)`
**Docstring:** Semantic search via MCP with confidence filtering and sorting.

#### `cmd_write` (agents/cursor/cursor_memory_client.py:427)
**Signature:** `def cmd_write(content: str, kind: str, thread_id: str | None, scope: str, tags: list[str] | None)`
**Docstring:** Write to memory via MCP using PacketEnvelope v2.0 schema.

#### `cmd_session` (agents/cursor/cursor_memory_client.py:482)
**Signature:** `def cmd_session()`
**Docstring:** Show current daily session ID.

#### `cmd_mcp_test` (agents/cursor/cursor_memory_client.py:498)
**Signature:** `def cmd_mcp_test()`
**Docstring:** MCP Round-Trip Test — Write + Search via MCP tools only.

*... and 50 more functions*

### Key Imports (Dependencies)
```
__future__
abc
agents.cursor.cursor_client
agents.cursor.cursor_memory_client
agents.cursor.cursor_memory_kernel
agents.cursor.extractors.base_extractor
agents.cursor.extractors.cursor_action_extractor
agents.cursor.gmp_meta_learning
agents.cursor.integrations.cursor_gateway
agents.cursor.integrations.cursor_langgraph
argparse
asyncio
base64
base_extractor
core.config_constants
core.decorators
core.governance.approval_manager
core.governance.mistake_prevention
core.schemas
core.singleton_auto_registry
cursor_memory_client
dataclasses
datetime
enum
hashlib
json
langgraph.graph
logging
memory.checkpoint.cursor_checkpoint_manager
memory.governance_gate
# ... and 21 more imports
```

### Constants
- `WORKING_MEMORY` = 'working_memory' (agents/cursor/cursor_retrieval_kernel.py)
- `LONG_TERM_MEMORY` = 'long_term_memory' (agents/cursor/cursor_retrieval_kernel.py)
- `REPO_SCAN` = 'repo_scan' (agents/cursor/cursor_retrieval_kernel.py)
- `L2` = 'L2' (agents/cursor/gmp_meta_learning.py)
- `L3` = 'L3' (agents/cursor/gmp_meta_learning.py)
- `L4` = 'L4' (agents/cursor/gmp_meta_learning.py)
- `L5` = 'L5' (agents/cursor/gmp_meta_learning.py)
- `DEFAULT_LESSONS_PATH` = ... (agents/cursor/ingest_lessons.py)
- `TIER_MAP` = {...} (agents/cursor/ingest_lessons.py)
- `SCHEMA_VERSION` = '2.0.0' (agents/cursor/cursor_memory_client.py)
- `SUPPORTED_VERSIONS` = [...] (agents/cursor/cursor_memory_client.py)
- `CURSOR_SESSION_NAMESPACE` = ... (agents/cursor/cursor_memory_client.py)
- `MCP_URL` = ... (agents/cursor/cursor_memory_client.py)
- `L9_API_URL` = ... (agents/cursor/cursor_memory_client.py)
- `L9_EXECUTOR_API_KEY` = ... (agents/cursor/cursor_memory_client.py)

### Public API (`__all__` exports)
```python
__all__ = [
    "AutonomyController",
    "AutonomyGraduationMetrics",
    "AutonomyLevel",
    "CursorClient",
    "CursorMemoryKernel",
    "GMPExecutionResult",
    "GMPMetaLearningEngine",
    "LearnedHeuristic",
    "Lesson",
    "SessionState",
    "TodoItem",
    "activate_session",
    "create_cursor_memory_kernel",
    "get_active_kernel",
    "BaseExtractor",
    "CursorActionExtractor",
]
```

### DORA Governance Metadata
```yaml
component_name: Cursor Action Extractor
module_version: 1.0.0
created_by: Igor Beylin
created_at: 2025-12-09T01:02:49Z
updated_at: 2026-01-14T16:23:10Z
layer: intelligence
domain: agent_execution
module_name: cursor_action_extractor
type: collector
status: active
```

---

## GENERATION INSTRUCTIONS

Generate a README with these EXACT sections:

### Required Sections

1. **Overview** (1-2 paragraphs)
   - What this module does
   - Who depends on it
   - Use the class names and purposes from the facts

2. **Responsibilities and Boundaries**
   - What this module owns (derive from classes)
   - What it does NOT do (based on imports/dependencies)
   - Dependencies table (Inbound/Outbound)

3. **Directory Layout**
   - Use the file list provided
   - Add brief descriptions based on class/function purposes

4. **Key Components**
   - For each major class, include:
     - Class name and file
     - Docstring (from facts)
     - Key methods with signatures
     - If Pydantic: list fields with types

5. **Data Models and Contracts**
   - List all Pydantic models with fields
   - Include field types and defaults
   - State invariants (derive from field constraints)

6. **API Surface** (if routes exist)
   - List all routes with method, path, handler
   - Include request/response types if visible

7. **Configuration**
   - Feature flags (L9_ENABLE_*)
   - Environment variables

8. **Observability**
   - Logging format
   - Metrics to emit

9. **AI Usage Rules**
   - ✅ Allowed: Application logic, tests
   - ⚠️ Restricted: Schema changes
   - ❌ Forbidden: `__init__.py`, core entry points

---

## VALIDATION CHECKLIST

After generating, verify:

- [ ] Every class mentioned exists in the facts above
- [ ] Every method signature matches the extracted signatures
- [ ] Every file path is from the file list
- [ ] No invented classes, methods, or files
- [ ] Pydantic fields match exactly

---

## OUTPUT FORMAT

Return ONLY the README content in markdown format.
Start with `# Cursor Module` heading.
End with generation timestamp.

Do NOT include this prompt in the output.
Do NOT add commentary before or after the README.

---

**BEGIN GENERATION**
