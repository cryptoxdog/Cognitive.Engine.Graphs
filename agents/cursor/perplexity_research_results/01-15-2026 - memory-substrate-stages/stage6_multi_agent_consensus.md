# Stage 6: Multi-Agent Belief-Calibrated Consensus System

**Perplexity Deep Research Output**
**Generated: 2026-01-15**
**Component ID: STAGE-6-BCCS**

---

## Overview

Production-Grade Multi-Agent Belief-Calibrated Consensus System (BCCS) for LLM Coordination featuring:
- Confidence calibration using ECE (Expected Calibration Error)
- Weighted voting with domain expertise
- Byzantine-resilient consensus protocols
- Maximum 10 rounds with convergence guarantees
- PostgreSQL-backed complete audit trails
- Leader election for tie-breaking

## Core Components

| Component | Purpose | L9 Target Location |
|-----------|---------|-------------------|
| `BeliefCalibrator` | Compute calibration scores from historical accuracy | `memory/belief_calibrator.py` |
| `ConsensusSeeker` | Multi-round BCCS protocol implementation | `memory/consensus_seeker.py` |
| `LeaderSelector` | Deterministic leader election for tie-breaking | `memory/leader_selector.py` |

## Data Models (Pydantic v2)

### Calibration Models

```python
@dataclass
class CalibrationScore:
    """Quantifies an agent's calibration quality and reliability."""
    agent_id: str
    domain: str
    confidence_score: float  # 0.0-1.0, how well confidence aligns with accuracy
    domain_expertise: float  # 0.0-1.0, experience in this domain
    recent_accuracy: float   # 0.0-1.0, recent correctness rate
    ece_metric: float        # 0.0-1.0, Expected Calibration Error (lower = better)
    sample_count: int
    samples_in_domain: int
    last_updated: datetime

    @property
    def combined_weight(self) -> float:
        """Combined weight for consensus voting."""
        base_weight = self.confidence_score * (1.0 - self.ece_metric)
        domain_adjustment = 0.5 + 0.5 * (self.samples_in_domain / max(self.sample_count, 1))
        return base_weight * domain_adjustment
```

### Proposal Models

```python
class AgentProposal(BaseModel):
    """Represents a single agent's proposal in a consensus round."""
    agent_id: str
    round_number: int = Field(ge=1, le=10)
    proposed_value: str
    verbalized_confidence: float = Field(ge=0.0, le=1.0)
    calibration_score: Optional[CalibrationScore] = None
    reasoning_trace: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class ConsensusDecision(BaseModel):
    """Final consensus decision with full provenance."""
    operation_id: UUID
    problem_description: str
    final_decision: str
    decision_confidence: float = Field(ge=0.0, le=1.0)
    convergence_round: int = Field(ge=1, le=10)
    leader_selected: bool
    leading_agent_id: Optional[str] = None
    achieving_weight_threshold: float
    proposals_by_round: List[List[AgentProposal]]
    stability_confirmed: bool
    timestamp: datetime
    metadata: dict
```

## BeliefCalibrator Implementation

Computes calibration scores reflecting agent reliability:

### Calibration Metrics

1. **Expected Calibration Error (ECE)**
   - Measures alignment between confidence and accuracy
   - Lower ECE = better calibrated
   - Computed per (agent, domain) pair

```python
def _compute_ece(self, confidences: List[float], correctness: List[int], bins: int = 10) -> float:
    """
    Compute Expected Calibration Error.

    For each confidence bin [0.0-0.1, 0.1-0.2, ...]:
    - Calculate average confidence in bin
    - Calculate actual accuracy in bin
    - ECE = weighted average of |confidence - accuracy|
    """
```

2. **Confidence-Accuracy Correlation**
   - Pearson correlation between expressed confidence and correctness
   - Higher correlation = better calibrated

### Database Query Pattern

```sql
SELECT
    ao.operation_id,
    ao.final_decision,
    ap.proposed_value,
    ap.verbalized_confidence,
    CASE WHEN ao.final_decision = ap.proposed_value THEN 1 ELSE 0 END as was_correct
FROM agent_proposals ap
JOIN consensus_operations ao ON ap.operation_id = ao.operation_id
WHERE ap.agent_id = $1 AND ao.problem_domain = $2
ORDER BY ao.timestamp DESC
LIMIT $3
```

## ConsensusSeeker Implementation

Multi-round BCCS protocol:

### Protocol Parameters

```python
MAX_ROUNDS = 10          # Maximum iterations
WEIGHT_THRESHOLD = 0.70  # 70% weighted agreement required
STABILITY_ROUNDS = 2     # Agreement must persist across 2 rounds
```

### Consensus Pipeline

```
1. Initialize operation in database
2. Compute calibration scores for all agents
3. For each round (1 to MAX_ROUNDS):
   a. Collect proposals from all agents (concurrent)
   b. Include peer context from previous round
   c. Check convergence:
      - Compute weighted vote totals
      - Leading proposal weight > WEIGHT_THRESHOLD?
      - Agreement stable across STABILITY_ROUNDS?
   d. If converged → break
4. If no consensus → invoke leader selection
5. Persist decision to database
6. Return ConsensusDecision with full provenance
```

### Weighted Voting Algorithm

```python
def _check_convergence(self, proposals, round_number, previous_rounds):
    # Compute weighted vote totals
    vote_weights = {}
    for proposal in proposals:
        weight = proposal.calibration_score.combined_weight if proposal.calibration_score else 0.5
        vote_weights[proposal.proposed_value] = vote_weights.get(proposal.proposed_value, 0.0) + weight

    # Normalize
    total_weight = sum(vote_weights.values()) or 1.0
    vote_weights = {v: w / total_weight for v, w in vote_weights.items()}

    # Find leading proposal
    leading_value = max(vote_weights.items(), key=lambda x: x[1])[0]
    leading_weight = vote_weights[leading_value]

    # Check threshold
    meets_threshold = leading_weight >= self.WEIGHT_THRESHOLD

    # Check stability across previous rounds
    if meets_threshold and len(previous_rounds) >= self.STABILITY_ROUNDS - 1:
        # Verify leading proposal consistent across rounds
        stable = all(prev_leading == leading_value for prev_leading in ...)
        return {"converged": stable, ...}
```

## LeaderSelector Implementation

Deterministic leader election for tie-breaking:

```python
@staticmethod
def select_leader(agents: List[str], calibration_scores: Dict[str, CalibrationScore]) -> str:
    """
    Deterministically select leader from pool of agents.

    Ranking criteria (lexicographic):
    1. combined_weight (DESC)
    2. domain_expertise (DESC)
    3. recency of updates (DESC)
    """
    rankings = [
        (agent_id, score.combined_weight, score.domain_expertise, score.last_updated)
        for agent_id in agents
        if agent_id in calibration_scores
    ]
    rankings.sort(key=lambda x: (-x[1], -x[2], -x[3].timestamp()))
    return rankings[0][0]
```

## Database Schema

```sql
CREATE TABLE consensus_operations (
    operation_id UUID PRIMARY KEY,
    problem_description TEXT NOT NULL,
    problem_domain VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    final_decision TEXT,
    decision_confidence FLOAT,
    convergence_round INTEGER,
    leader_selected BOOLEAN DEFAULT FALSE,
    leading_agent_id VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);

CREATE TABLE agent_proposals (
    id SERIAL PRIMARY KEY,
    operation_id UUID NOT NULL REFERENCES consensus_operations(operation_id),
    agent_id VARCHAR(255) NOT NULL,
    round_number INTEGER NOT NULL,
    proposed_value TEXT NOT NULL,
    verbalized_confidence FLOAT NOT NULL,
    reasoning_trace TEXT,
    calibration_score_json JSONB,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE agent_calibration_history (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    domain VARCHAR(100) NOT NULL,
    measurement_period_start TIMESTAMP NOT NULL,
    measurement_period_end TIMESTAMP NOT NULL,
    accuracy_rate FLOAT NOT NULL,
    confidence_accuracy_correlation FLOAT,
    ece_metric FLOAT,
    sample_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    UNIQUE(agent_id, domain, measurement_period_start)
);
```

## Byzantine Fault Tolerance

The system maintains safety guarantees when:
- Total weight of faulty agents < 1/3 total system weight
- Unlike classical BFT (requires 3/4 honest participants)
- Weighted voting allows higher tolerance for low-weighted faulty nodes

## L9 Adaptation Notes

### Integration Points

1. **PostgreSQL**: Use existing L9 database pool
2. **Agent Executor**: Integrate with L9's agent execution framework
3. **Logging**: Use structlog with L9 patterns
4. **Metrics**: Integrate with L9 telemetry

### Required Changes for L9

- Replace `asyncpg` pool with L9's database abstraction
- Integrate agent_executor with L9's AgentExecutorService
- Add PacketEnvelope logging for consensus decisions
- Wire calibration history to existing agent metrics
- Consider integration with L9's multi-agent orchestration

### Mapping to L9 Concepts

| BCCS Concept | L9 Equivalent |
|--------------|---------------|
| Agent | AgentInstance |
| Domain | Task category / Tool domain |
| Calibration | Agent performance metrics |
| Consensus | Multi-agent task resolution |

## Research Foundations

- **Google DeepMind**: Multi-agent coordination research
- **Agent2Agent Protocol**: Google Cloud Next 2025
- **RLHF Calibration**: Confidence miscalibration post-RLHF
- **Weighted BFT**: Performance-weighted Byzantine fault tolerance
- **Recursive Debate**: Multi-agent refinement semantics

---

*Research source: Perplexity deep_research tool, 2026-01-15*
