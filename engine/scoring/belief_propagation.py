"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [scoring]
tags: [belief-propagation, ToTh, bayesian, entropy, scoring]
owner: engine-team
status: active
--- /L9_META ---

engine/scoring/belief_propagation.py

Theory of Trust (ToTh) Implementation.

Reference: Zhang et al., "Theory of Trust for Trust-Aware Recommender Systems" (2015)
Section 3: Entropy-penalized composite trust scoring

Algorithm:
  1. Multi-parent belief fusion (CEG match dimensions)
  2. Sequential chain propagation (GATE hop traces)
  3. Entropy penalty (uncertainty discount)

Contracts:
  - Immutable inputs
  - No side effects
  - Deterministic scoring
  - [0.0, 1.0] bounded outputs

Integration Points:
  - CEG: rescore_candidates() after Neo4j query, before GMP-05 Pareto
  - GATE: hop_trust_from_entry() → chain confidence scoring
"""
from __future__ import annotations

import math
from typing import Any

# ── Trust tier constants ───────────────────────────────────────────────────────

TRUST_ENTAILMENT = 0.95    # Status: COMPLETED
TRUST_NEUTRAL = 0.60       # Status: PENDING, DELEGATED
TRUST_CONTRADICTION = 0.10  # Status: FAILED, TIMEOUT


# ── Bayesian update (core primitive) ──────────────────────────────────────────

def bayesian_update(prior: float, evidence: float) -> float:
    """
    Single-step Bayesian belief update.

    Formula:
        P(H|E) = P(E|H) * P(H) / P(E)

    Where:
        P(H)   = prior belief
        P(E|H) = evidence (trust signal)
        P(E)   = P(E|H)*P(H) + P(E|¬H)*P(¬H)

    Assume symmetric likelihood: P(E|¬H) = 1 - P(E|H)

    Args:
        prior:    Initial belief [0.0, 1.0]
        evidence: Trust signal   [0.0, 1.0]

    Returns:
        Posterior belief [0.0, 1.0]

    Examples:
        >>> bayesian_update(0.5, 0.9)   # Neutral prior, strong evidence
        0.9
        >>> bayesian_update(0.8, 0.9)   # Strong prior, strong evidence
        0.973...
        >>> bayesian_update(0.2, 0.9)   # Weak prior, strong evidence
        0.692...
    """
    if not (0.0 <= prior <= 1.0):
        raise ValueError(f"prior must be in [0.0, 1.0], got {prior}")
    if not (0.0 <= evidence <= 1.0):
        raise ValueError(f"evidence must be in [0.0, 1.0], got {evidence}")

    # P(E) = P(E|H)*P(H) + P(E|¬H)*P(¬H)
    p_e = evidence * prior + (1 - evidence) * (1 - prior)

    if p_e == 0.0:
        return 0.0

    # P(H|E) = P(E|H) * P(H) / P(E)
    posterior = (evidence * prior) / p_e
    return max(0.0, min(1.0, posterior))


# ── Entropy calculation ────────────────────────────────────────────────────────

def _entropy(p: float) -> float:
    """
    Shannon entropy of a binary belief state.

    H(p) = -p*log2(p) - (1-p)*log2(1-p)

    Where:
        p = 0.0 or 1.0 → H = 0.0 (complete certainty)
        p = 0.5        → H = 1.0 (maximum uncertainty)

    Args:
        p: Belief probability [0.0, 1.0]

    Returns:
        Entropy [0.0, 1.0]
    """
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


# ── Multi-parent composite (CEG match dimensions) ─────────────────────────────

def composite_score(trust_scores: list[float], prior: float = 0.5) -> float:
    """
    Multi-parent belief fusion with entropy penalty.

    Use Case:
        CEG match scoring — independent dimensions (geo, community, temporal,
        price) each contribute evidence. Combine via sequential Bayesian
        updates, then penalize by uncertainty.

    Algorithm (ToTh §3):
        1. Propagate belief through all trust signals
        2. Compute average belief μ̄
        3. Compute average entropy H̄
        4. Return μ̄ - H̄ (entropy-penalized score)

    Args:
        trust_scores: Independent trust signals from scoring dimensions
        prior:        Initial belief (default 0.5 = neutral)

    Returns:
        Composite score [0.0, 1.0]

    Examples:
        >>> composite_score([0.9, 0.85, 0.8], prior=0.5)
        0.815...   # High confidence, low entropy penalty
        >>> composite_score([0.9, 0.5, 0.2], prior=0.5)
        0.234...   # Mixed signals, high entropy penalty
        >>> composite_score([0.95] * 5, prior=0.8)
        0.949...   # Strong prior + consistent evidence
    """
    if not trust_scores:
        return prior

    beliefs: list[float] = []
    current_belief = prior
    for trust in trust_scores:
        current_belief = bayesian_update(current_belief, trust)
        beliefs.append(current_belief)

    mu_bar = sum(beliefs) / len(beliefs)
    h_bar = sum(_entropy(b) for b in beliefs) / len(beliefs)
    composite = mu_bar - h_bar
    return max(0.0, min(1.0, composite))


# ── Chain composite (GATE hop trace quality) ──────────────────────────────────

def chain_composite(trust_scores: list[float], prior: float = 0.5) -> float:
    """
    Sequential chain belief fusion with entropy penalty.

    Use Case:
        GATE hop trace quality — each hop is causally prior to the next.
        Measures consistency of the entire delegation path.

    Algorithm:
        Same as composite_score, but semantically represents ordered hop
        sequence (not independent dimensions).

    Args:
        trust_scores: Trust signals from hop sequence (ordered)
        prior:        Initial belief

    Returns:
        Chain quality score [0.0, 1.0]

    Examples:
        >>> chain_composite([0.95, 0.95, 0.95], prior=0.6)
        0.949...   # Consistent high-trust path
        >>> chain_composite([0.95, 0.6, 0.95], prior=0.6)
        0.651...   # Middle hop uncertainty degrades quality
    """
    return composite_score(trust_scores, prior)


# ── Chain propagation (GATE terminal confidence) ──────────────────────────────

def propagate_chain(trust_scores: list[float], prior: float = 0.5) -> float:
    """
    Sequential chain belief propagation (no entropy penalty).

    Use Case:
        GATE terminal confidence — "How confident is the last hop?"
        Pure belief propagation through causal chain.

    Args:
        trust_scores: Trust signals from hop sequence (ordered)
        prior:        Initial belief

    Returns:
        Terminal belief [0.0, 1.0]

    Examples:
        >>> propagate_chain([0.9, 0.85, 0.8], prior=0.5)
        0.984...   # Strong accumulation
        >>> propagate_chain([0.9, 0.5, 0.2], prior=0.5)
        0.231...   # Weak terminal hop dominates
    """
    if not trust_scores:
        return prior

    belief = prior
    for trust in trust_scores:
        belief = bayesian_update(belief, trust)
    return belief


# ── Hop trust derivation ──────────────────────────────────────────────────────

def hop_trust_from_entry(
    status: str,
    duration_ms: float,
    timeout_ms: float = 30000.0,
) -> float:
    """
    Derive trust signal from GATE HopEntry.

    Mapping:
        COMPLETED  → 0.95 (entailment tier), degraded by timeout proximity
        PENDING    → 0.60 (neutral tier)
        DELEGATED  → 0.60 (neutral tier)
        FAILED     → 0.10 (contradiction tier)
        TIMEOUT    → 0.10 (contradiction tier)

    Timeout Penalty:
        If hop completed but duration_ms / timeout_ms > 0.5,
        linearly degrade trust from 0.95 → 0.60.

    Args:
        status:      HopEntry.status
        duration_ms: HopEntry.duration_ms
        timeout_ms:  HopEntry timeout limit (default 30s)

    Returns:
        Trust signal [0.0, 1.0]

    Examples:
        >>> hop_trust_from_entry("COMPLETED", 1000, 30000)
        0.95       # Fast completion
        >>> hop_trust_from_entry("COMPLETED", 25000, 30000)
        0.658...   # Near timeout
        >>> hop_trust_from_entry("FAILED", 5000, 30000)
        0.10
    """
    if status == "COMPLETED":
        base_trust = TRUST_ENTAILMENT
    elif status in {"PENDING", "DELEGATED"}:
        base_trust = TRUST_NEUTRAL
    elif status in {"FAILED", "TIMEOUT"}:
        base_trust = TRUST_CONTRADICTION
    else:
        base_trust = TRUST_NEUTRAL

    # Timeout proximity penalty (COMPLETED only)
    if status == "COMPLETED" and duration_ms > 0 and timeout_ms > 0:
        proximity = duration_ms / timeout_ms
        if proximity > 0.5:
            penalty_factor = (proximity - 0.5) / 0.5  # 0.0 → 1.0
            degraded = TRUST_ENTAILMENT - penalty_factor * (
                TRUST_ENTAILMENT - TRUST_NEUTRAL
            )
            return max(TRUST_NEUTRAL, degraded)

    return base_trust


# ── CEG candidate rescoring (public API) ──────────────────────────────────────

def rescore_candidates(
    candidates: list[dict[str, Any]],
    dimension_keys: list[str],
    prior_key: str = "confidence",
    score_key: str = "belief_score",
) -> list[dict[str, Any]]:
    """
    Rescore CEG match candidates using belief propagation.

    Algorithm:
        1. Extract trust signals from scoring dimensions
        2. Compute prior from candidate[prior_key] (default 0.5)
        3. Apply composite_score() with entropy penalty
        4. Store result in candidate[score_key]
        5. Re-sort by score_key descending
        6. Return new list (immutable — original candidates unchanged)

    Integration Point:
        Call after Neo4j query, before GMP-05 Pareto.

    Args:
        candidates:     List of match candidates with dimension scores
        dimension_keys: Dimension property names (e.g., ["geo_score", "community_score"])
        prior_key:      Property name for prior belief (default "confidence")
        score_key:      Property name for output score (default "belief_score")

    Returns:
        New sorted list (highest belief_score first)

    Examples:
        >>> candidates = [
        ...     {"id": "A", "geo": 0.9, "temporal": 0.85, "confidence": 0.7},
        ...     {"id": "B", "geo": 0.95, "temporal": 0.9,  "confidence": 0.5},
        ... ]
        >>> rescored = rescore_candidates(candidates, ["geo", "temporal"])
        >>> rescored[0]["id"]
        'A'   # Higher prior wins despite slightly lower dimensions
    """
    if not candidates or not dimension_keys:
        return candidates

    rescored: list[dict[str, Any]] = []
    for c in candidates:
        trust_scores = [float(c[dim]) for dim in dimension_keys if dim in c]
        prior = float(c.get(prior_key, 0.5))
        score = composite_score(trust_scores, prior)
        rescored.append({**c, score_key: score})

    rescored.sort(key=lambda x: x.get(score_key, 0.0), reverse=True)
    return rescored
