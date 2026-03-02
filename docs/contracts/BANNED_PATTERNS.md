<!-- L9_TEMPLATE: true -->
# L9 Banned Patterns (Comprehensive)

Quick-reference for ALL agents. If you see yourself writing any of these, STOP.

## Imports
| ❌ Banned | ✅ Instead | Why |
|-----------|-----------|-----|
| `from fastapi import ...` (in engine/) | Register handlers in `engine/handlers.py` | Chassis owns HTTP |
| `from starlette import ...` | Nothing — chassis handles middleware | Chassis owns middleware |
| `import uvicorn` | Nothing — chassis runs uvicorn | Chassis owns ASGI |
| `from engine.api import ...` | `from engine.handlers import ...` | engine/api/ is deleted |

## Security
| ❌ Banned | ✅ Instead | Why |
|-----------|-----------|-----|
| `eval(expr)` | Dispatch table with explicit operators | Code injection |
| `exec(code)` | Never needed in engine | Code injection |
| `compile(code)` | Never needed in engine | Code injection |
| `f"MATCH (n:{label})"` without sanitize | `f"MATCH (n:{sanitize_label(label)})"` | Cypher injection |
| `f"... LIMIT {top_n}"` | `"... LIMIT $limit"` + params | Cypher injection |
| `pickle.loads()` | `json.loads()` | Deserialization attack |
| `yaml.load()` (without Loader) | `yaml.safe_load()` | YAML deserialization |

## Architecture
| ❌ Banned | ✅ Instead | Why |
|-----------|-----------|-----|
| Custom FastAPI routes | `register_handler("action", handler_fn)` | L9 chassis contract |
| Tenant resolution in engine | Receive `tenant` as handler arg | Chassis resolves tenant |
| CORS/auth/rate-limit in engine | Nothing — chassis provides | Chassis owns all HTTP concerns |
| `Depends(resolve_tenant)` | `tenant: str` handler parameter | No FastAPI in engine |
| Creating `engine/api/` directory | Don't | Chassis owns API surface |
| Creating `engine/middleware.py` | Don't | Chassis owns middleware |

## Code Quality
| ❌ Banned | ✅ Instead | Why |
|-----------|-----------|-----|
| `except:` (bare) | `except SpecificError as e:` | Silent failures |
| `except Exception: pass` | `except Exception: logger.error(...); raise` | Swallowed errors |
| `return None` from validators | `raise ValueError(...)` | Silent validation bypass |
| `# TODO` / `# FIXME` / `pass` in non-abstract | Implement or raise `NotImplementedError` | Dead code / stubs |
| `from typing import Any` (when type is known) | Use specific type | Type safety |

## Naming
| ❌ Banned | ✅ Instead | Why |
|-----------|-----------|-----|
| `matchentities` (flatcase) | `match_entities` (snake_case) | FIELD_NAMES.md contract |
| `nullBehavior` (camelCase) | `null_behavior` (snake_case) | FIELD_NAMES.md contract |
| `Field(alias="...")` | Use snake_case directly | PYDANTIC_YAML_MAPPING.md |
| `candidateprop` | `field` (per GateSpec) | FIELD_NAMES.md contract |
```
