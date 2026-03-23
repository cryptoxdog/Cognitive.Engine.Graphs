"""
L9 GMP v2.0 Meta-Learning Engine
================================

Production-ready implementation of the GMP v2.0 meta-learning system for
autonomous execution pattern analysis and heuristic generation.

This module powers the learning-driven autonomy evolution in GMP v2.0+
Fully type-safe, truly async, tested for production deployment on L9.

Author: L9 Frontier Research
Version: 2.1.0
Status: Production Ready
Updated: 2026-01-15 (async conversion)
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Gmp Meta Learning",
    "module_version": "2.1.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-15T23:45:01Z",
    "updated_at": "2026-01-17T23:47:56Z",
    "layer": "intelligence",
    "domain": "data_models",
    "module_name": "gmp_meta_learning",
    "type": "enum",
    "status": "production",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": ["PostgreSQL"],
        "memory_layers": [],
        "imported_by": [
            "agents.cursor.__init__",
            "api.routes.gmp_learning",
            "api.server",
            "tests.cursor.test_gmp_meta_learning",
        ],
    },
}
# ============================================================================

import os
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog
from core.decorators import must_stay_async
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = structlog.get_logger(__name__)

# ============================================================================
# DATA MODELS (Pydantic v2)
# ============================================================================


class AutonomyLevel(StrEnum):
    """Graduated autonomy levels in GMP v2.0."""

    L2 = "L2"  # Constrained Execution
    L3 = "L3"  # Adaptive Execution
    L4 = "L4"  # Meta-Strategic Execution
    L5 = "L5"  # Fully Autonomous


class GMPExecutionResult(BaseModel):
    """Results from a completed GMP execution."""

    model_config = ConfigDict(str_strip_whitespace=True)

    gmp_id: str = Field(..., description="Unique GMP execution ID")
    task_type: str = Field(..., description="Type of task (refactor, schema, feature, etc.)")
    todo_count: int = Field(..., ge=0, description="Number of TODO items in plan")
    execution_minutes: float = Field(..., ge=0, description="Total execution time in minutes")
    error_count: int = Field(0, ge=0, description="Number of errors encountered")
    error_types: list[str] = Field(default_factory=list, description="Types of errors")
    files_modified: list[str] = Field(default_factory=list, description="Files modified")
    lines_changed: int = Field(0, ge=0, description="Total lines changed")
    final_confidence: float = Field(..., ge=0, le=100, description="Audit confidence score")
    audit_result: str = Field(..., description="PASS, CONDITIONAL, or FAIL")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Execution timestamp")
    l9_kernel_versions: dict[str, str] = Field(default_factory=dict, description="Kernel versions at execution")
    feature_flags_enabled: list[str] = Field(default_factory=list, description="Enabled feature flags")


class LearnedHeuristic(BaseModel):
    """A heuristic pattern learned from prior executions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    heuristic_id: str = Field(default_factory=lambda: str(uuid_module.uuid4()))
    pattern_text: str = Field(..., description="Human-readable pattern description")
    condition: str = Field(..., description="When this heuristic applies")
    recommendation: str = Field(..., description="What to do when condition is true")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score for this heuristic")
    supporting_gmp_ids: list[str] = Field(default_factory=list, description="GMPs validating this heuristic")
    impact_estimate: str = Field(..., description="Expected impact (faster, fewer_errors, safer, etc.)")
    generated_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = Field(True, description="Whether this heuristic is currently used")

    def __hash__(self):
        """Make hashable for deduplication."""
        return hash(self.pattern_text)


class AutonomyGraduationMetrics(BaseModel):
    """Tracks metrics for autonomy level graduation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    current_level: AutonomyLevel = Field(AutonomyLevel.L2, description="Current autonomy level")
    perfect_executions_l2: int = Field(0, ge=0, description="Consecutive perfect L2 executions")
    consistency_score_l3: float = Field(0, ge=0, le=1, description="L3 consistency metric")
    safety_audit_passed_l4: bool = Field(False, description="L4 safety audit status")

    # Graduation prerequisites
    l2_to_l3_ready: bool = Field(False, description="Can graduate to L3?")
    l3_to_l4_ready: bool = Field(False, description="Can graduate to L4?")
    l4_to_l5_ready: bool = Field(False, description="Can graduate to L5?")

    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ============================================================================
# DATABASE MODELS (SQLAlchemy Async)
# ============================================================================

Base = declarative_base()


class GMPExecutionHistoryDB(Base):
    """Stores execution history in PostgreSQL."""

    __tablename__ = "gmp_execution_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    gmp_id = Column(String(255), nullable=False, unique=True, index=True)
    task_type = Column(String(100), nullable=False, index=True)
    todo_count = Column(Integer, nullable=False)
    execution_minutes = Column(Float, nullable=False)
    error_count = Column(Integer, nullable=False, default=0)
    error_types = Column(ARRAY(String), nullable=False, default=list)
    files_modified = Column(ARRAY(String), nullable=False, default=list)
    lines_changed = Column(Integer, nullable=False, default=0)
    final_confidence = Column(Float, nullable=False)
    audit_result = Column(String(20), nullable=False)
    l9_kernel_versions = Column(JSONB, nullable=False, default=dict)
    feature_flags_enabled = Column(ARRAY(String), nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    __table_args__ = (
        Index("idx_task_type_confidence", "task_type", "final_confidence"),
        Index("idx_error_type_analysis", "error_count", "created_at"),
    )


class LearnedHeuristicDB(Base):
    """Stores learned heuristics in PostgreSQL."""

    __tablename__ = "learned_heuristics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    heuristic_id = Column(String(255), nullable=False, unique=True, index=True)
    pattern_text = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    recommendation = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, index=True)
    supporting_gmp_ids = Column(ARRAY(String), nullable=False, default=list)
    impact_estimate = Column(String(50), nullable=False)
    generated_date = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    active = Column(Boolean, nullable=False, default=True, index=True)


class AutonomyMetricsDB(Base):
    """Stores autonomy graduation metrics in PostgreSQL."""

    __tablename__ = "autonomy_graduation_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
    current_level = Column(String(10), nullable=False, default=AutonomyLevel.L2.value)
    perfect_executions_l2 = Column(Integer, nullable=False, default=0)
    consistency_score_l3 = Column(Float, nullable=False, default=0.0)
    safety_audit_passed_l4 = Column(Boolean, nullable=False, default=False)
    l2_to_l3_ready = Column(Boolean, nullable=False, default=False)
    l3_to_l4_ready = Column(Boolean, nullable=False, default=False)
    l4_to_l5_ready = Column(Boolean, nullable=False, default=False)
    last_updated = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


# ============================================================================
# META-LEARNING ENGINE (Async)
# ============================================================================


class GMPMetaLearningEngine:
    """
    Processes GMP execution history to extract patterns and generate heuristics.

    Responsibilities:
    1. Log each execution to database
    2. Analyze patterns (weekly)
    3. Generate/update heuristics
    4. Track autonomy graduation metrics
    5. Provide recommendations to next GMP

    Note: All methods are truly async using SQLAlchemy async session.
    """

    def __init__(self, database_url: str):
        """
        Initialize learning engine with async database connection.

        Args:
            database_url: PostgreSQL connection string (use postgresql+asyncpg://)
        """
        # Convert sync URL to async if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self._logger = structlog.get_logger(__name__)

        logger.info(
            "GMPMetaLearningEngine initialized (async)",
            db_url=database_url.split("@")[-1],
        )

    async def create_tables(self) -> None:
        """Create all tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("GMP learning tables created/verified")

    @must_stay_async("callers use await")
    async def log_execution(self, result: GMPExecutionResult) -> bool:
        """
        Log a GMP execution result to the database.

        Args:
            result: Execution results to log

        Returns:
            True if logged successfully
        """
        try:
            async with self.async_session() as session:
                db_record = GMPExecutionHistoryDB(
                    gmp_id=result.gmp_id,
                    task_type=result.task_type,
                    todo_count=result.todo_count,
                    execution_minutes=result.execution_minutes,
                    error_count=result.error_count,
                    error_types=result.error_types,
                    files_modified=result.files_modified,
                    lines_changed=result.lines_changed,
                    final_confidence=result.final_confidence,
                    audit_result=result.audit_result,
                    l9_kernel_versions=result.l9_kernel_versions,
                    feature_flags_enabled=result.feature_flags_enabled,
                    created_at=result.created_at,
                )
                session.add(db_record)
                await session.commit()

            logger.info(
                "GMP execution logged",
                gmp_id=result.gmp_id,
                task_type=result.task_type,
                confidence=result.final_confidence,
            )
            return True

        except Exception as e:
            logger.exception("Failed to log execution", error=str(e))
            return False

    async def analyze_execution_patterns(self) -> dict[str, Any]:
        """
        Analyze all logged executions to find patterns.

        Returns:
            Dictionary with pattern analysis results
        """
        try:
            async with self.async_session() as session:
                # Get all executions from past 30 days
                threshold_date = datetime.now(UTC) - timedelta(days=30)

                stmt = select(GMPExecutionHistoryDB).where(GMPExecutionHistoryDB.created_at >= threshold_date)
                result = await session.execute(stmt)
                executions = result.scalars().all()

                if not executions:
                    logger.warning("No recent executions to analyze")
                    return {"total_executions": 0}

                # Calculate statistics
                exec_list = list(executions)
                stats = {
                    "total_executions": len(exec_list),
                    "avg_execution_time": sum(e.execution_minutes for e in exec_list) / len(exec_list),
                    "avg_confidence": sum(e.final_confidence for e in exec_list) / len(exec_list),
                    "error_rate": sum(1 for e in exec_list if e.error_count > 0) / len(exec_list),
                    "pass_rate": sum(1 for e in exec_list if e.audit_result == "PASS") / len(exec_list),
                }

                # Analyze by task type
                by_task_type = {}
                for task_type in {e.task_type for e in exec_list}:
                    task_execs = [e for e in exec_list if e.task_type == task_type]
                    by_task_type[task_type] = {
                        "count": len(task_execs),
                        "avg_time": sum(e.execution_minutes for e in task_execs) / len(task_execs),
                        "avg_confidence": sum(e.final_confidence for e in task_execs) / len(task_execs),
                    }

                stats["by_task_type"] = by_task_type

            logger.info("Pattern analysis complete", stats=stats)
            return stats

        except Exception as e:
            logger.exception("Failed to analyze patterns", error=str(e))
            return {}

    async def generate_heuristics(self) -> list[LearnedHeuristic]:
        """
        Generate new heuristics from execution patterns.

        Returns:
            List of new/updated heuristics with high confidence
        """
        heuristics: list[LearnedHeuristic] = []

        try:
            async with self.async_session() as session:
                threshold_date = datetime.now(UTC) - timedelta(days=30)

                stmt = select(GMPExecutionHistoryDB).where(GMPExecutionHistoryDB.created_at >= threshold_date)
                result = await session.execute(stmt)
                executions = list(result.scalars().all())

                if not executions:
                    return []

                # Heuristic 1: Large TODO counts correlate with longer execution
                todo_counts = [e.todo_count for e in executions]
                exec_times = [e.execution_minutes for e in executions]

                if len(todo_counts) > 2:
                    correlation = self._calculate_correlation(todo_counts, exec_times)
                    if correlation > 0.7:
                        heuristics.append(
                            LearnedHeuristic(
                                pattern_text=f"TODO count strongly correlates with execution time (r={correlation:.2f})",
                                condition="if todo_count > 20",
                                recommendation="allocate 180+ minutes, add Phase 5 verification buffer",
                                confidence=0.87,
                                supporting_gmp_ids=[e.gmp_id for e in executions[:5]],
                                impact_estimate="faster_phase_planning",
                            )
                        )

                # Heuristic 2: Certain error types are predictable by task type
                error_by_type: dict[str, list[str]] = {}
                for e in executions:
                    if e.task_type not in error_by_type:
                        error_by_type[e.task_type] = []
                    if e.error_types:
                        error_by_type[e.task_type].extend(e.error_types)

                for task_type, errors in error_by_type.items():
                    if errors:
                        error_freq = {err: errors.count(err) for err in set(errors)}
                        top_error = max(error_freq, key=lambda k: error_freq[k])
                        confidence = error_freq[top_error] / len(errors)

                        if confidence > 0.6:
                            heuristics.append(
                                LearnedHeuristic(
                                    pattern_text=f"Task type '{task_type}' frequently encounters {top_error}",
                                    condition=f"if task_type == '{task_type}'",
                                    recommendation=f"pre-verify {top_error} prevention measures",
                                    confidence=confidence,
                                    supporting_gmp_ids=[e.gmp_id for e in executions if e.task_type == task_type][:3],
                                    impact_estimate="fewer_errors",
                                )
                            )

                # Heuristic 3: High confidence scores predict low future errors
                high_conf_execs = [e for e in executions if e.final_confidence >= 95]
                if high_conf_execs:
                    error_rate_high = sum(1 for e in high_conf_execs if e.error_count > 0) / len(high_conf_execs)
                    if error_rate_high < 0.1:
                        heuristics.append(
                            LearnedHeuristic(
                                pattern_text="High audit confidence (≥95%) predicts error-free execution",
                                condition="if audit_confidence >= 95",
                                recommendation="prioritize for faster approval, skip extra verification",
                                confidence=0.92,
                                supporting_gmp_ids=[e.gmp_id for e in high_conf_execs[:5]],
                                impact_estimate="faster_approval",
                            )
                        )

                # Store heuristics
                for h in heuristics:
                    db_record = LearnedHeuristicDB(
                        heuristic_id=h.heuristic_id,
                        pattern_text=h.pattern_text,
                        condition=h.condition,
                        recommendation=h.recommendation,
                        confidence=h.confidence,
                        supporting_gmp_ids=h.supporting_gmp_ids,
                        impact_estimate=h.impact_estimate,
                        generated_date=h.generated_date,
                        active=h.active,
                    )
                    session.add(db_record)

                await session.commit()

            logger.info("Heuristics generated", count=len(heuristics))
            return heuristics

        except Exception as e:
            logger.exception("Failed to generate heuristics", error=str(e))
            return []

    async def get_active_heuristics(self) -> list[LearnedHeuristic]:
        """
        Retrieve all active heuristics for use in next GMP.

        Returns:
            List of active heuristics sorted by confidence
        """
        try:
            async with self.async_session() as session:
                stmt = (
                    select(LearnedHeuristicDB)
                    .where(LearnedHeuristicDB.active.is_(True))
                    .order_by(LearnedHeuristicDB.confidence.desc())
                )
                result = await session.execute(stmt)
                db_heuristics = result.scalars().all()

                return [
                    LearnedHeuristic(
                        heuristic_id=h.heuristic_id,
                        pattern_text=h.pattern_text,
                        condition=h.condition,
                        recommendation=h.recommendation,
                        confidence=h.confidence,
                        supporting_gmp_ids=h.supporting_gmp_ids or [],
                        impact_estimate=h.impact_estimate,
                        generated_date=h.generated_date,
                        active=h.active,
                    )
                    for h in db_heuristics
                ]

        except Exception as e:
            logger.exception("Failed to retrieve heuristics", error=str(e))
            return []

    async def update_autonomy_metrics(self, execution: GMPExecutionResult) -> AutonomyGraduationMetrics:
        """
        Update autonomy graduation metrics after execution.

        Args:
            execution: The GMP execution that just completed

        Returns:
            Updated metrics
        """
        try:
            async with self.async_session() as session:
                # Get current metrics or create new
                stmt = select(AutonomyMetricsDB)
                result = await session.execute(stmt)
                metrics = result.scalar_one_or_none()

                if not metrics:
                    metrics = AutonomyMetricsDB()
                    session.add(metrics)

                # Check for perfect execution (no errors, confidence >= 95, audit PASS)
                is_perfect = (
                    execution.error_count == 0 and execution.final_confidence >= 95 and execution.audit_result == "PASS"
                )

                if is_perfect:
                    metrics.perfect_executions_l2 += 1
                else:
                    metrics.perfect_executions_l2 = 0  # Reset on imperfect execution

                # Check L2→L3 graduation (10 consecutive perfect executions)
                if metrics.perfect_executions_l2 >= 10:
                    metrics.l2_to_l3_ready = True

                # Check L3→L4 graduation (consistency score >= 0.95)
                recent_stmt = select(GMPExecutionHistoryDB).order_by(GMPExecutionHistoryDB.created_at.desc()).limit(10)
                recent_result = await session.execute(recent_stmt)
                recent_execs = list(recent_result.scalars().all())

                if len(recent_execs) >= 5:
                    confidences = [e.final_confidence for e in recent_execs]
                    avg_conf = sum(confidences) / len(confidences)
                    variance = sum((c - avg_conf) ** 2 for c in confidences) / len(confidences)
                    std_dev = variance**0.5
                    consistency = 1.0 - (std_dev / 100)
                    metrics.consistency_score_l3 = max(0.0, min(1.0, consistency))

                    if metrics.consistency_score_l3 >= 0.95:
                        metrics.l3_to_l4_ready = True

                metrics.last_updated = datetime.now(UTC)
                await session.commit()

                # Refresh to get updated values
                await session.refresh(metrics)

                return AutonomyGraduationMetrics(
                    current_level=AutonomyLevel(metrics.current_level),
                    perfect_executions_l2=metrics.perfect_executions_l2,
                    consistency_score_l3=metrics.consistency_score_l3,
                    safety_audit_passed_l4=metrics.safety_audit_passed_l4,
                    l2_to_l3_ready=metrics.l2_to_l3_ready,
                    l3_to_l4_ready=metrics.l3_to_l4_ready,
                    l4_to_l5_ready=metrics.l4_to_l5_ready,
                )

        except Exception as e:
            logger.exception("Failed to update autonomy metrics", error=str(e))
            raise

    @staticmethod
    def _calculate_correlation(x: list[float], y: list[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x) < 2 or len(y) < 2 or len(x) != len(y):
            return 0.0

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denom_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denom_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if denom_x == 0 or denom_y == 0:
            return 0.0

        return numerator / (denom_x * denom_y)


# ============================================================================
# AUTONOMY CONTROLLER (Async)
# ============================================================================


class AutonomyController:
    """
    Manages autonomy level graduation and feature flag enforcement.

    Ensures L2→L3→L4→L5 progression only when prerequisites are met.
    """

    def __init__(self, learning_engine: GMPMetaLearningEngine):
        """Initialize with reference to learning engine."""
        self.learning_engine = learning_engine
        self._logger = structlog.get_logger(__name__)

    async def get_current_autonomy_level(self) -> AutonomyLevel:
        """
        Determine current autonomy level based on metrics.

        Returns:
            Current autonomy level
        """
        try:
            async with self.learning_engine.async_session() as session:
                stmt = select(AutonomyMetricsDB)
                result = await session.execute(stmt)
                metrics = result.scalar_one_or_none()

                if not metrics:
                    return AutonomyLevel.L2

                # Determine highest ready level
                if metrics.l4_to_l5_ready:
                    return AutonomyLevel.L5
                if metrics.l3_to_l4_ready:
                    return AutonomyLevel.L4
                if metrics.l2_to_l3_ready:
                    return AutonomyLevel.L3
                return AutonomyLevel.L2

        except Exception as e:
            self._logger.exception("Failed to get autonomy level", error=str(e))
            return AutonomyLevel.L2

    async def assert_capability(self, feature: str) -> bool:
        """
        Check if a feature is enabled at current autonomy level.

        Args:
            feature: Feature name (e.g., "adaptive_todos", "architectural_reasoning")

        Returns:
            True if feature is enabled
        """
        current_level = await self.get_current_autonomy_level()

        feature_map = {
            "adaptive_todos": AutonomyLevel.L3,
            "failure_recovery": AutonomyLevel.L3,
            "architectural_reasoning": AutonomyLevel.L4,
            "optimization_suggestions": AutonomyLevel.L4,
            "autonomous_goal": AutonomyLevel.L5,
            "self_healing": AutonomyLevel.L5,
        }

        required_level = feature_map.get(feature, AutonomyLevel.L2)

        # Compare ordinal values
        level_order = {"L2": 0, "L3": 1, "L4": 2, "L5": 3}
        is_enabled = level_order[current_level.value] >= level_order[required_level.value]

        self._logger.info(
            "Capability assertion",
            feature=feature,
            current_level=current_level.value,
            required_level=required_level.value,
            enabled=is_enabled,
        )

        return is_enabled

    async def can_graduate_to_next_level(self) -> tuple[bool, str | None]:
        """
        Check if system can graduate to next autonomy level.

        Returns:
            (can_graduate, required_action_or_none)
        """
        try:
            async with self.learning_engine.async_session() as session:
                stmt = select(AutonomyMetricsDB)
                result = await session.execute(stmt)
                metrics = result.scalar_one_or_none()

                if not metrics:
                    return False, "No metrics found"

                current = AutonomyLevel(metrics.current_level)

                if current == AutonomyLevel.L2 and metrics.l2_to_l3_ready:
                    return (
                        True,
                        "Ready to graduate L2→L3 (10 perfect executions achieved)",
                    )
                if current == AutonomyLevel.L3 and metrics.l3_to_l4_ready:
                    return True, "Ready to graduate L3→L4 (consistency >= 95% achieved)"
                if current == AutonomyLevel.L4 and metrics.l4_to_l5_ready:
                    return True, "Ready to graduate L4→L5 (safety audit passed)"
                if current == AutonomyLevel.L2:
                    needed = 10 - metrics.perfect_executions_l2
                    return False, f"Need {needed} more perfect executions for L2→L3"
                if current == AutonomyLevel.L3:
                    needed = max(0, int(95 - metrics.consistency_score_l3 * 100))
                    return False, f"Need {needed}% more consistency for L3→L4"
                return False, "Safety audit required for L4→L5"

        except Exception as e:
            self._logger.exception("Failed to check graduation readiness", error=str(e))
            return False, str(e)

    async def graduate_to_next_level(self) -> tuple[bool, str]:
        """
        Attempt to graduate to the next autonomy level.

        Returns:
            (success, message)
        """
        can_graduate, reason = await self.can_graduate_to_next_level()

        if not can_graduate:
            return False, f"Cannot graduate: {reason}"

        try:
            async with self.learning_engine.async_session() as session:
                stmt = select(AutonomyMetricsDB)
                result = await session.execute(stmt)
                metrics = result.scalar_one_or_none()

                if not metrics:
                    return False, "No metrics found"

                current = AutonomyLevel(metrics.current_level)

                if current == AutonomyLevel.L2:
                    metrics.current_level = AutonomyLevel.L3.value
                    new_level = "L3"
                elif current == AutonomyLevel.L3:
                    metrics.current_level = AutonomyLevel.L4.value
                    new_level = "L4"
                elif current == AutonomyLevel.L4:
                    metrics.current_level = AutonomyLevel.L5.value
                    new_level = "L5"
                else:
                    return False, "Already at maximum level L5"

                metrics.last_updated = datetime.now(UTC)
                await session.commit()

                self._logger.info(f"Graduated to autonomy level {new_level}")
                return True, f"Successfully graduated to {new_level}"

        except Exception as e:
            self._logger.exception("Failed to graduate", error=str(e))
            return False, str(e)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


async def main():
    """Example demonstrating GMP v2.0 learning engine (async)."""

    # Initialize engine (requires PostgreSQL with asyncpg)
    # Note: URL is auto-converted to postgresql+asyncpg:// — set DATABASE_URL in the environment.
    engine = GMPMetaLearningEngine(
        database_url=os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/l9"),
    )

    # Create tables
    await engine.create_tables()

    # Log an execution
    result = GMPExecutionResult(
        gmp_id="GMP-90-Migration-2026-01-15",
        task_type="migration",
        todo_count=4,
        execution_minutes=15.5,
        error_count=0,
        error_types=[],
        files_modified=[
            "migrations/0021_gmp_learning.sql",
            "core/gmp/meta_learning_engine.py",
        ],
        lines_changed=500,
        final_confidence=98.0,
        audit_result="PASS",
        feature_flags_enabled=["L9_GMP_LEARNING"],
        l9_kernel_versions={"10-packet-protocol": "1.0.0"},
    )

    await engine.log_execution(result)

    # Analyze patterns
    stats = await engine.analyze_execution_patterns()
    logger.info("pattern analysis: stats", stats=stats)

    # Generate heuristics
    heuristics = await engine.generate_heuristics()
    logger.info("generated {len(heuristics)} heuristics")

    # Get active heuristics for next GMP
    active = await engine.get_active_heuristics()
    logger.info("active heuristics: {len(active)}")

    # Update autonomy metrics
    metrics = await engine.update_autonomy_metrics(result)
    logger.info("updated metrics: metrics", metrics=metrics)

    # Check autonomy level
    controller = AutonomyController(engine)
    level = await controller.get_current_autonomy_level()
    logger.info("current autonomy level: level", level=level)

    # Check if can graduate
    can_grad, reason = await controller.can_graduate_to_next_level()
    logger.info("can graduate: can grad (reason)", can_grad=can_grad, reason=reason)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-019",
    "governance_level": "high",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": [
        "async",
        "data-models",
        "engine",
        "enum",
        "event-driven",
        "intelligence",
        "logging",
        "messaging",
        "metrics",
        "migration",
    ],
    "keywords": [
        "active",
        "analysis",
        "analyze",
        "assert",
        "async",
        "autonomy",
        "can",
        "capability",
    ],
    "business_value": "This module powers the learning-driven autonomy evolution in GMP v2.0+ Fully type-safe, truly async, tested for production deployment on L9. Author: L9 Frontier Research Version: 2.1.0 Status: Product",
    "last_modified": "2026-01-17T23:47:56Z",
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
