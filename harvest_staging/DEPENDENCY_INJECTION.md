<!-- L9_TEMPLATE: true -->
# L9 Dependency Injection Contract

## Rule
Engine dependencies (GraphDriver, DomainPackLoader, Redis) are injected
ONCE at startup via `init_dependencies()`. Handlers access them via module-level
references. No singletons, no service locators, no FastAPI Depends.

## Pattern (Current)
```python
# engine/handlers.py
_graph_driver: GraphDriver | None = None
_domain_loader: DomainPackLoader | None = None

def init_dependencies(graph_driver: GraphDriver, domain_loader: DomainPackLoader) -> None:
    global _graph_driver, _domain_loader
    _graph_driver = graph_driver
    _domain_loader = domain_loader
```


## Chassis Startup Sequence

```python
# chassis/app.py (or equivalent startup hook)
from engine.handlers import init_dependencies, register_all

async def lifespan(app):
    driver = GraphDriver(uri=settings.NEO4J_URI, ...)
    loader = DomainPackLoader(domains_dir=settings.DOMAINS_DIR)
    init_dependencies(driver, loader)
    register_all(chassis_router)
    yield
    await driver.close()
```


## BANNED Patterns

```python
# ❌ No creating drivers inside handlers
async def handle_match(tenant, payload):
    driver = GraphDriver(...)  # BANNED — creates new connection per request

# ❌ No importing settings directly in engine modules
from chassis.settings import get_settings  # BANNED — chassis concern

# ❌ No FastAPI Depends in engine code
from fastapi import Depends  # BANNED — chassis concern
```

```

