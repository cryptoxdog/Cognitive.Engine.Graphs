# GMP Action: Add GMP Learning API Routes

**GMP ID:** GMP-93
**Tier:** RUNTIME_TIER
**Risk:** Low
**Estimated Time:** 30 min
**Depends On:** GMP-92 (Wire Learning Engine)

---

## VARIABLE BINDINGS

```yaml
TASK_NAME: add_gmp_learning_routes
EXECUTION_SCOPE: Create api/routes/gmp_learning.py with endpoints for GMP learning system
RISK_LEVEL: Low
IMPACT_METRICS: API surface area, GMP learning accessibility
```

---

## CONTEXT

The GMP learning engine needs API endpoints for:

- Viewing current autonomy level
- Checking graduation status
- Getting active heuristics
- Viewing execution history analytics

---

## TODO PLAN

### [T1] Create api/routes/gmp_learning.py

- **File:** `api/routes/gmp_learning.py`
- **Lines:** 1-150
- **Action:** Create
- **Change:** New router with endpoints

### [T2] Wire router to api/server.py

- **File:** `api/server.py`
- **Lines:** Router includes section
- **Action:** Insert
- **Change:** Add `from api.routes.gmp_learning import router as gmp_learning_router`
- **Change:** Add `app.include_router(gmp_learning_router, prefix="/api/gmp", tags=["gmp-learning"])`

---

## FILE CONTENT: api/routes/gmp_learning.py

```python
"""
GMP Learning API Routes
=======================

Endpoints for GMP v2.0 meta-learning system.

Endpoints:
- GET /api/gmp/autonomy-level - Current autonomy level
- GET /api/gmp/graduation-status - Can graduate to next level?
- GET /api/gmp/heuristics - Active learned heuristics
- GET /api/gmp/analytics - Execution pattern analytics
- POST /api/gmp/log-execution - Log a GMP execution (internal)
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog

from core.gmp import (
    GMPMetaLearningEngine,
    AutonomyController,
    AutonomyLevel,
    GMPExecutionResult,
    LearnedHeuristic,
    AutonomyGraduationMetrics,
)
from config.settings import settings

logger = structlog.get_logger(__name__)
router = APIRouter()


# Response models
class AutonomyLevelResponse(BaseModel):
    current_level: str
    description: str
    capabilities: List[str]


class GraduationStatusResponse(BaseModel):
    can_graduate: bool
    reason: str
    current_level: str
    next_level: Optional[str]


class HeuristicsResponse(BaseModel):
    count: int
    heuristics: List[Dict[str, Any]]


class AnalyticsResponse(BaseModel):
    total_executions: int
    avg_execution_time: float
    avg_confidence: float
    error_rate: float
    pass_rate: float
    by_task_type: Dict[str, Any]


# Dependency to get engine
def get_gmp_engine() -> GMPMetaLearningEngine:
    from api.server import gmp_learning_engine
    if gmp_learning_engine is None:
        raise HTTPException(
            status_code=503,
            detail="GMP Learning Engine not initialized. Set L9_GMP_LEARNING_ENABLED=true"
        )
    return gmp_learning_engine


# Level descriptions
LEVEL_INFO = {
    "L2": {
        "description": "Constrained Execution",
        "capabilities": ["locked_todo_plans", "static_audit", "no_learning"]
    },
    "L3": {
        "description": "Adaptive Execution",
        "capabilities": ["adaptive_todos", "failure_recovery", "pattern_matching"]
    },
    "L4": {
        "description": "Meta-Strategic Execution",
        "capabilities": ["architectural_reasoning", "optimization_suggestions", "cross_gmp_analysis"]
    },
    "L5": {
        "description": "Fully Autonomous",
        "capabilities": ["autonomous_goal", "self_healing", "proactive_improvements"]
    },
}


@router.get("/autonomy-level", response_model=AutonomyLevelResponse)
async def get_autonomy_level(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Get current GMP autonomy level."""
    controller = AutonomyController(engine)
    level = await controller.get_current_autonomy_level()

    info = LEVEL_INFO.get(level.value, LEVEL_INFO["L2"])

    return AutonomyLevelResponse(
        current_level=level.value,
        description=info["description"],
        capabilities=info["capabilities"]
    )


@router.get("/graduation-status", response_model=GraduationStatusResponse)
async def get_graduation_status(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Check if system can graduate to next autonomy level."""
    controller = AutonomyController(engine)

    current = await controller.get_current_autonomy_level()
    can_graduate, reason = await controller.can_graduate_to_next_level()

    next_level_map = {"L2": "L3", "L3": "L4", "L4": "L5", "L5": None}

    return GraduationStatusResponse(
        can_graduate=can_graduate,
        reason=reason,
        current_level=current.value,
        next_level=next_level_map.get(current.value)
    )


@router.post("/graduate", response_model=GraduationStatusResponse)
async def graduate_to_next_level(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Attempt to graduate to the next autonomy level."""
    controller = AutonomyController(engine)

    success, message = await controller.graduate_to_next_level()
    current = await controller.get_current_autonomy_level()

    next_level_map = {"L2": "L3", "L3": "L4", "L4": "L5", "L5": None}

    return GraduationStatusResponse(
        can_graduate=success,
        reason=message,
        current_level=current.value,
        next_level=next_level_map.get(current.value)
    )


@router.get("/heuristics", response_model=HeuristicsResponse)
async def get_heuristics(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Get all active learned heuristics."""
    heuristics = await engine.get_active_heuristics()

    return HeuristicsResponse(
        count=len(heuristics),
        heuristics=[
            {
                "heuristic_id": h.heuristic_id,
                "pattern": h.pattern_text,
                "condition": h.condition,
                "recommendation": h.recommendation,
                "confidence": h.confidence,
                "impact": h.impact_estimate,
                "supporting_gmps": len(h.supporting_gmp_ids),
            }
            for h in heuristics
        ]
    )


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Get GMP execution analytics for past 30 days."""
    stats = await engine.analyze_execution_patterns()

    if stats.get("total_executions", 0) == 0:
        return AnalyticsResponse(
            total_executions=0,
            avg_execution_time=0.0,
            avg_confidence=0.0,
            error_rate=0.0,
            pass_rate=0.0,
            by_task_type={}
        )

    return AnalyticsResponse(
        total_executions=stats["total_executions"],
        avg_execution_time=stats["avg_execution_time"],
        avg_confidence=stats["avg_confidence"],
        error_rate=stats["error_rate"],
        pass_rate=stats["pass_rate"],
        by_task_type=stats.get("by_task_type", {})
    )


@router.post("/log-execution")
async def log_execution(
    result: GMPExecutionResult,
    engine: GMPMetaLearningEngine = Depends(get_gmp_engine)
):
    """Log a GMP execution result (internal use)."""
    success = await engine.log_execution(result)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to log execution")

    # Update autonomy metrics
    metrics = await engine.update_autonomy_metrics(result)

    return {
        "logged": True,
        "gmp_id": result.gmp_id,
        "autonomy_metrics": {
            "current_level": metrics.current_level.value,
            "perfect_executions": metrics.perfect_executions_l2,
            "l2_to_l3_ready": metrics.l2_to_l3_ready,
        }
    }


@router.post("/generate-heuristics")
async def trigger_heuristic_generation(engine: GMPMetaLearningEngine = Depends(get_gmp_engine)):
    """Manually trigger heuristic generation from execution history."""
    heuristics = await engine.generate_heuristics()

    return {
        "generated": len(heuristics),
        "heuristics": [
            {
                "pattern": h.pattern_text,
                "confidence": h.confidence,
            }
            for h in heuristics
        ]
    }
```

---

## VALIDATION

- [ ] `py_compile api/routes/gmp_learning.py`
- [ ] Server starts without errors
- [ ] `curl http://localhost:8000/api/gmp/autonomy-level` returns 200
- [ ] `curl http://localhost:8000/api/gmp/graduation-status` returns 200

---

## EXPECTED ENDPOINTS

| Method | Path                           | Description                  |
| ------ | ------------------------------ | ---------------------------- |
| GET    | `/api/gmp/autonomy-level`      | Current level (L2/L3/L4/L5)  |
| GET    | `/api/gmp/graduation-status`   | Can graduate?                |
| POST   | `/api/gmp/graduate`            | Attempt graduation           |
| GET    | `/api/gmp/heuristics`          | Active learned heuristics    |
| GET    | `/api/gmp/analytics`           | 30-day execution analytics   |
| POST   | `/api/gmp/log-execution`       | Log GMP result               |
| POST   | `/api/gmp/generate-heuristics` | Trigger heuristic generation |
