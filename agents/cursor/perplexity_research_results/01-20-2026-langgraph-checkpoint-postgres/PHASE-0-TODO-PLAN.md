# GMP-105: LangGraph Checkpoint Resilience — Phase 0 TODO Plan

**Date:** 2026-01-20
**Tier:** RUNTIME_TIER
**Priority:** 🔴 HIGH
**Scope:** `memory/checkpoint/`

---

## 📚 Knowledge Sources Integrated

| Source | Type | Key Insights |
|--------|------|--------------|
| LangGraph Persistence Docs | @DOCS (official) | BaseCheckpointSaver interface, `.put()`, `.get_tuple()`, `.list()`, `.put_writes()` |
| PostgreSQL Vacuuming Docs | @DOCS (official) | Autovacuum tuning, `autovacuum_vacuum_scale_factor`, TTL patterns |
| Perplexity Deep Research | Gap-bridge | Connection pool exhaustion incidents, retry patterns, pool health monitoring |
| L9 Current Implementation | Codebase | `L9PostgresSaver`, `CheckpointValidator`, `CheckpointMetrics` |

---

## 📊 Gap Analysis Summary

### ✅ Covered by @DOCS (No Perplexity needed)

| Topic | Source | Status in L9 |
|-------|--------|--------------|
| `BaseCheckpointSaver` interface | LangGraph Docs | ✅ Implemented in `L9PostgresSaver` |
| `.put()`, `.get()` methods | LangGraph Docs | ✅ Implemented |
| Thread + checkpoint_id pattern | LangGraph Docs | ✅ Using `cursor:{thread_id}` |
| VACUUM basics | PostgreSQL Docs | ✅ Understood |
| Memory Store for cross-thread | LangGraph Docs | ⚠️ Not yet implemented |
| Encryption via `LANGGRAPH_AES_KEY` | LangGraph Docs | ❌ Not implemented |
| Semantic search in Store | LangGraph Docs | ⚠️ L9 has pgvector separately |

### 🔍 Bridged by Perplexity Research

| Topic | Gap in Docs | Perplexity Finding |
|-------|-------------|-------------------|
| Pool exhaustion | Not documented | 10+ GitHub issues, pool depletes after ~10 runs |
| Retry wrapper | Not in official docs | `RetryableAsyncPostgresCheckpointer` pattern |
| Pool health monitoring | Not in official docs | `pool_available`, `pool_size` metrics |
| `list()` stub issue | Not discussed | L9 returns `[]`, should query `cursor:*` pattern |
| TTL cleanup scale | Brief mention | ~8 checkpoints per message, aggressive cleanup needed |

---

## 🎯 Phase 0 TODO Plan (LOCKED)

### Batch 1: Production Resilience (HIGH PRIORITY)

| ID | TODO | File | Action | Lines | Tests |
|----|------|------|--------|-------|-------|
| **[v1.0-001]** | Add `L9RetryablePostgresSaver` wrapper class | `memory/checkpoint/postgres_saver.py` | INSERT | +80 | 3 unit tests |
| **[v1.0-002]** | Implement `_execute_with_retry()` method | `memory/checkpoint/postgres_saver.py` | INSERT | +35 | Covered by 001 |
| **[v1.0-003]** | Add retry to `put()` method | `memory/checkpoint/postgres_saver.py` | WRAP | +5 | Covered by 001 |
| **[v1.0-004]** | Add retry to `get()` method | `memory/checkpoint/postgres_saver.py` | WRAP | +5 | Covered by 001 |
| **[v1.0-005]** | Implement `list()` method properly | `memory/checkpoint/postgres_saver.py` | REPLACE | +40 | 2 unit tests |
| **[v1.0-006]** | Add `get_pool_stats()` method | `memory/checkpoint/postgres_saver.py` | INSERT | +15 | 1 unit test |

### Batch 2: Observability Enhancement

| ID | TODO | File | Action | Lines | Tests |
|----|------|------|--------|-------|-------|
| **[v1.0-007]** | Add pool stats to `CheckpointMetrics` | `memory/checkpoint_metrics.py` | INSERT | +25 | 1 unit test |
| **[v1.0-008]** | Add `CHECKPOINT_POOL_*` Prometheus gauges | `memory/checkpoint_metrics.py` | INSERT | +15 | Covered by 007 |
| **[v1.0-009]** | Integrate pool stats into server health endpoint | `api/server.py` | INSERT | +10 | 1 integration test |

### Batch 3: Documentation

| ID | TODO | File | Action | Lines | Tests |
|----|------|------|--------|-------|-------|
| **[v1.0-010]** | Update CHECKPOINT-OPS-RUNBOOK with pool monitoring | `readme/CHECKPOINT-OPS-RUNBOOK.md` | INSERT | +30 | N/A |
| **[v1.0-011]** | Add TTL cleanup guidance | `readme/CHECKPOINT-OPS-RUNBOOK.md` | INSERT | +20 | N/A |

---

## 📋 Implementation Spec

### [v1.0-001] L9RetryablePostgresSaver

**Source:** Perplexity research line 99-163

```python
class L9RetryablePostgresSaver(L9PostgresSaver):
    """L9PostgresSaver with automatic retry + exponential backoff."""

    def __init__(
        self,
        repository: Optional[SubstrateRepository] = None,
        max_retries: int = 3,
        base_retry_delay: float = 0.1,
    ):
        super().__init__(repository)
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
```

### [v1.0-005] list() Implementation

**Source:** LangGraph docs + L9 pattern

```python
async def list(
    self,
    config: Dict[str, Any],
    filter: Optional[Dict[str, Any]] = None,
    before: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """List checkpoints for thread (LangGraph interface)."""
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return []

    agent_id_pattern = f"cursor:{thread_id}"
    # Query repository for matching checkpoints
    checkpoints = await self._repository.list_checkpoints(
        agent_id_pattern=agent_id_pattern,
        limit=limit or 100,
    )
    return checkpoints
```

### [v1.0-007] Pool Stats Metrics

**Source:** Perplexity research line 176-194

```python
CHECKPOINT_POOL_SIZE = Gauge(
    "l9_checkpoint_pool_size",
    "Total connections in checkpoint pool",
)

CHECKPOINT_POOL_AVAILABLE = Gauge(
    "l9_checkpoint_pool_available",
    "Available connections in checkpoint pool",
)

CHECKPOINT_POOL_WAITING = Gauge(
    "l9_checkpoint_pool_requests_waiting",
    "Requests waiting for checkpoint pool connection",
)
```

---

## 🚫 Scope Boundaries

### MAY Modify
- `memory/checkpoint/postgres_saver.py`
- `memory/checkpoint_metrics.py`
- `readme/CHECKPOINT-OPS-RUNBOOK.md`
- `api/server.py` (health endpoint only)
- `tests/memory/test_checkpoint_*.py`

### MAY NOT Modify
- `memory/checkpoint_validator.py` (working correctly)
- `memory/checkpoint_manager.py` (thin wrapper, not touched)
- `migrations/*.sql` (no schema changes this GMP)
- Any files outside `memory/checkpoint/` scope

---

## ✅ Definition of Done

- [ ] All 11 TODOs implemented
- [ ] 8 new unit tests passing
- [ ] 1 integration test passing
- [ ] No regressions in existing checkpoint tests
- [ ] Pool stats visible in `/health` endpoint
- [ ] RUNBOOK updated with pool monitoring section
- [ ] py_compile passes on all modified files
- [ ] ruff check passes

---

## 📊 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Retry causes duplicate checkpoints | LOW | MEDIUM | Idempotent PUT via same checkpoint_id |
| Pool stats add overhead | LOW | LOW | Gauges are lightweight |
| list() query slow | MEDIUM | LOW | Add LIMIT, index exists |

---

## 🔗 Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| `langgraph-checkpoint` | ✅ Installed | Uses `BaseCheckpointSaver` |
| `prometheus_client` | ✅ Optional | Graceful fallback if missing |
| `SubstrateRepository` | ✅ Exists | Uses existing singleton |

---

## Next Steps

1. **CONFIRM** this Phase 0 plan
2. **Phase 1:** Baseline verification (existing tests pass)
3. **Phase 2:** Implement Batch 1 (TODOs 001-006)
4. **Phase 3:** Implement Batch 2 (TODOs 007-009)
5. **Phase 4:** Implement Batch 3 (TODOs 010-011)
6. **Phase 5:** Validation (all tests pass)
7. **Phase 6:** Generate GMP report

---

**Plan Status:** 🔒 LOCKED
**Ready for:** `/gmp` execution
