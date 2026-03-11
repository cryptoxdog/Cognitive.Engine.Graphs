<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

**Closes:** Agents creating custom loggers, random metric names

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Observability Contract

## Rule
All logging, metrics, and tracing are handled by the chassis. Engines NEVER
configure logging, create Prometheus counters, or manage trace context.

## Structured Log Fields (automatic via chassis)
Every log line emitted by the chassis includes:
```json
{
  "timestamp": "2026-03-01T20:00:00Z",
  "level": "info",
  "event": "request_processed",
  "trace_id": "abc-123-def",
  "tenant": "plasticos",
  "action": "match",
  "node": "graph-engine",
  "execution_ms": 45.2
}
```


## Engine Logging Pattern

```python
import logging
logger = logging.getLogger(__name__)

# ✅ CORRECT — use stdlib logger, chassis configures structlog
logger.info("Gate compilation complete", extra={
    "gate_count": 14,
    "match_direction": "buyer_to_seller",
})

# ❌ WRONG — configuring logging in engine
import structlog
structlog.configure(...)                    # BANNED — chassis does this

# ❌ WRONG — creating custom formatters
logging.basicConfig(format="...")           # BANNED — chassis does this
```


## Prometheus Metrics (chassis-owned)

These metrics are auto-exported. Engines MUST NOT create their own.


| Metric | Type | Labels |
| :-- | :-- | :-- |
| `l9_request_total` | Counter | `action`, `tenant`, `status` |
| `l9_request_duration_seconds` | Histogram | `action`, `tenant` |
| `l9_request_errors_total` | Counter | `action`, `tenant`, `error_type` |

## Engine Custom Metrics (if absolutely needed)

```python
# Register via chassis metric factory — never create raw Prometheus objects
from chassis.metrics import register_histogram

gate_compilation_time = register_histogram(
    "l9_gate_compilation_seconds",       # MUST start with l9_
    "Time to compile all gates",
    labels=["tenant", "match_direction"],
)
```


## Trace Propagation

- `trace_id` is set by the chassis on inbound request
- Passed to engine via `payload` or context
- Included in all delegated packets automatically
- Engines NEVER generate their own trace IDs

```
