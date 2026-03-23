# GMP Action: Wire GMP Learning Engine to API Server

**GMP ID:** GMP-92
**Tier:** RUNTIME_TIER
**Risk:** Low
**Estimated Time:** 15 min

---

## VARIABLE BINDINGS

```yaml
TASK_NAME: wire_gmp_learning_engine
EXECUTION_SCOPE: Add GMPMetaLearningEngine initialization to api/server.py lifespan
RISK_LEVEL: Low
IMPACT_METRICS: GMP learning availability at runtime
```

---

## CONTEXT

The `core/gmp/meta_learning_engine.py` module is 100% instantiated but not wired to the API server. This GMP adds initialization to the FastAPI lifespan.

**Source Module:** `core/gmp/meta_learning_engine.py`
**Target:** `api/server.py`

---

## TODO PLAN

### [T1] Add import to api/server.py

- **File:** `api/server.py`
- **Lines:** Import section (top)
- **Action:** Insert
- **Change:** Add `from core.gmp import GMPMetaLearningEngine`

### [T2] Add global variable

- **File:** `api/server.py`
- **Lines:** After imports
- **Action:** Insert
- **Change:** Add `gmp_learning_engine: Optional[GMPMetaLearningEngine] = None`

### [T3] Initialize in lifespan startup

- **File:** `api/server.py`
- **Lines:** Inside `lifespan()` function, after other initializations
- **Action:** Insert
- **Change:** Add initialization block:

```python
# GMP Learning Engine
if settings.L9_GMP_LEARNING_ENABLED:
    global gmp_learning_engine
    gmp_learning_engine = GMPMetaLearningEngine(settings.DATABASE_URL)
    await gmp_learning_engine.create_tables()
    logger.info("GMP Learning Engine initialized")
```

### [T4] Add feature flag to config/settings.py

- **File:** `config/settings.py`
- **Lines:** Feature flags section
- **Action:** Insert
- **Change:** Add `L9_GMP_LEARNING_ENABLED: bool = False`

---

## VALIDATION

- [ ] `py_compile api/server.py`
- [ ] `py_compile config/settings.py`
- [ ] Server starts without errors
- [ ] With flag enabled: "GMP Learning Engine initialized" in logs

---

## EXPECTED OUTCOME

```python
# In api/server.py
from core.gmp import GMPMetaLearningEngine

gmp_learning_engine: Optional[GMPMetaLearningEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing init ...

    # GMP Learning Engine
    if settings.L9_GMP_LEARNING_ENABLED:
        global gmp_learning_engine
        gmp_learning_engine = GMPMetaLearningEngine(settings.DATABASE_URL)
        await gmp_learning_engine.create_tables()
        logger.info("GMP Learning Engine initialized")

    yield
    # ... cleanup ...
```
