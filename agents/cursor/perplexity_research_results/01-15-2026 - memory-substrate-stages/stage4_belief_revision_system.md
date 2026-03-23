# Stage 4: Explanation-Based Belief Revision System

**Perplexity Deep Research Output**
**Generated: 2026-01-15**
**Component ID: STAGE-4-BELIEF-REVISION**

---

## Overview

Production-Grade Explanation-Based Belief Revision System for LLM Memory integrating:
- Semantic contradiction detection using vector embeddings
- LLM-driven causal explanation generation
- Multi-strategy conflict resolution (REPLACE, BRANCH, MERGE, DEFER)
- Temporal versioning and historical fact management
- Neo4j + PostgreSQL persistence with full audit trails

## Core Components

| Component | Purpose | L9 Target Location |
|-----------|---------|-------------------|
| `ExplanationEngine` | Detect contradictions, generate causal explanations | `memory/explanation_engine.py` |
| `ConflictResolver` | Apply resolution strategies with persistence | `memory/conflict_resolver.py` |
| `MemorySystem` | High-level orchestration interface | `memory/belief_system.py` |

## Data Models (Pydantic v2)

### Enums

```python
class ConfidenceLevel(str, Enum):
    """Enumeration of confidence levels for assertions and explanations."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ContradictionType(str, Enum):
    """Types of contradictions that can be detected between facts."""
    DIRECT = "direct"  # Direct contradiction: A and NOT A
    SEMANTIC = "semantic"  # Semantic contradiction: incompatible meanings
    TEMPORAL = "temporal"  # Temporal contradiction: ordering conflicts
    CONDITIONAL = "conditional"  # Contradictory under specific conditions
    UNKNOWN = "unknown"


class ResolutionStrategy(str, Enum):
    """Strategies for resolving belief conflicts."""
    REPLACE = "replace"  # Replace old belief with new belief
    BRANCH = "branch"  # Both beliefs true in different contexts
    MERGE = "merge"  # Synthesize beliefs into unified representation
    DEFER = "defer"  # Escalate to human review
    IGNORE = "ignore"  # Accept contradiction without resolution
```

### Core Models

```python
class Fact(BaseModel):
    """Represents a single fact stored in the knowledge graph."""
    fact_id: UUID = Field(default_factory=uuid4)
    content: str = Field(..., min_length=1, max_length=4096)
    entity_type: str
    source_id: str
    source_authority: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_to: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)

    def is_currently_valid(self, as_of: Optional[datetime] = None) -> bool:
        check_time = as_of or datetime.now(timezone.utc)
        return self.valid_from <= check_time and (
            self.valid_to is None or self.valid_to > check_time
        )


class ConflictingFactPair(BaseModel):
    """Represents a pair of facts that conflict with each other."""
    fact_a_id: UUID
    fact_b_id: UUID
    contradiction_type: ContradictionType
    semantic_similarity: float = Field(ge=0.0, le=1.0)
    entity_overlap: float = Field(ge=0.0, le=1.0)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConflictExplanation(BaseModel):
    """Structured explanation of why two facts conflict and how to resolve."""
    explanation_id: UUID = Field(default_factory=uuid4)
    conflict_pair_id: UUID
    contradiction_type: ContradictionType
    causal_analysis: str = Field(..., min_length=10, max_length=2048)
    confidence_in_explanation: ConfidenceLevel
    source_authority_comparison: dict = Field(default_factory=dict)
    temporal_context: dict = Field(default_factory=dict)
    recommended_resolution: ResolutionStrategy
    resolution_reasoning: str = Field(..., min_length=10, max_length=2048)
    alternative_resolutions: list[tuple[ResolutionStrategy, str]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    llm_model_used: str


class ResolutionRecord(BaseModel):
    """Records the outcome of a belief conflict resolution."""
    resolution_id: UUID = Field(default_factory=uuid4)
    explanation_id: UUID
    selected_strategy: ResolutionStrategy
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fact_a_id: UUID
    fact_b_id: UUID
    outcome_fact_id: Optional[UUID] = None
    context_metadata: dict = Field(default_factory=dict)
    audit_log_entry: dict = Field(default_factory=dict)
```

## ExplanationEngine Implementation

Key methods:
- `detect_contradictions()` - Two-phase detection (semantic similarity + entity overlap)
- `generate_explanation()` - LLM-driven causal analysis with Claude
- `_classify_contradiction_type()` - Heuristic classification
- `_calibrate_confidence()` - Multi-signal confidence calibration

### Detection Algorithm

```
Phase 1: Semantic Similarity Filtering
├── Compute embeddings for new fact
├── Compare against existing facts using cosine similarity
├── Filter candidates exceeding similarity threshold (0.7)
└── Return candidate indices

Phase 2: Entity-Level Refinement
├── Extract entities from both facts using NER
├── Compute Jaccard similarity of entity sets
├── Filter candidates exceeding entity overlap threshold (0.3)
├── Classify contradiction type
└── Return ConflictingFactPair objects
```

## ConflictResolver Implementation

Key methods:
- `process_new_fact()` - Full pipeline: store → detect → explain → resolve → audit
- `_execute_replace_strategy()` - Invalidate old fact via valid_to timestamp
- `_execute_branch_strategy()` - Keep both facts with contextual metadata
- `_execute_merge_strategy()` - LLM-synthesize unified fact
- `_log_resolution_to_audit()` - Batched PostgreSQL audit logging

### Resolution Pipeline

```
1. Store new fact in Neo4j
2. Query existing facts by entity_type
3. Detect contradictions via ExplanationEngine
4. For each contradiction:
   a. Generate explanation with causal analysis
   b. Apply recommended resolution strategy
   c. Log to PostgreSQL audit trail
5. Return ResolutionRecord
```

## Theoretical Foundations

Based on AGM postulates (Alchourrón, Gärdenfors, Makinson):
- **Expansion**: Add belief without consistency checking
- **Revision**: Add belief while maintaining consistency
- **Contraction**: Remove belief with recovery property

Research references:
- AAAI 2025 reasoning panel on neuro-symbolic approaches
- FactConsolidation benchmark (6% accuracy on multi-hop conflicts)
- S3CDA semantic similarity-based conflict detection

## L9 Adaptation Notes

### Integration Points

1. **Neo4j**: Use existing graph connection from L9 infrastructure
2. **PostgreSQL**: Integrate with PacketStore for audit logging
3. **Embeddings**: Use existing pgvector infrastructure
4. **LLM Client**: Use existing Anthropic/OpenAI clients

### Required Changes for L9

- Replace `AsyncAnthropic` with L9's LLM client abstraction
- Integrate with `PacketEnvelope` for audit trail
- Use existing `MemorySubstrateService` patterns
- Add structlog integration following L9 patterns
- Implement as a new substrate layer

## Full Implementation Code

See source file for complete production code including:
- All Pydantic models
- ExplanationEngine class (~500 lines)
- ConflictResolver class (~600 lines)
- MemorySystem orchestrator
- Integration examples

---

*Research source: Perplexity deep_research tool, 2026-01-15*
