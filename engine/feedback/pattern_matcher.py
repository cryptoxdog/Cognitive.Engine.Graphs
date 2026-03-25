"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [feedback]
tags: [feedback, pattern-matching, jaccard]
owner: engine-team
status: active
--- /L9_META ---

Configuration pattern matcher using Jaccard similarity with sample
probability correction for frequency bias.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def corrected_similarity(
    raw_similarity: float,
    frequency: int,
    total_outcomes: int,
) -> float:
    """Apply sample probability correction to raw Jaccard similarity.

    Subtracts log(frequency)/log(total) to surface rare-but-predictive
    configurations over common ones.
    """
    if total_outcomes <= 1 or frequency <= 0:
        return raw_similarity
    correction = math.log(frequency) / math.log(total_outcomes)
    return max(0.0, raw_similarity - correction)


class ConfigurationMatcher:
    """
    Matches active match requests against historical outcome configurations
    using Jaccard similarity on dimension/gate profiles.

    When a new match request comes in, compares its gate+scoring configuration
    against historical TransactionOutcome configurations that resulted in
    positive outcomes. Returns similarity scores and pattern metadata.
    """

    def __init__(self, graph_driver: GraphDriver, domain_spec: DomainSpec) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._db = domain_spec.domain.id

    async def find_similar_outcomes(
        self,
        current_config: dict[str, Any],
        outcome_type: str = "success",
        similarity_threshold: float = 0.4,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find historical outcomes matching the current match configuration
        using Jaccard similarity on configuration keys with sample probability
        correction for frequency bias.
        """
        outcome_label = sanitize_label(self._spec.feedbackloop.outcome_node_label)

        cypher = f"""
        MATCH (o:{outcome_label})
        WHERE o.outcome = $outcome_type AND o.tenant = $tenant
        RETURN o.outcome_id AS outcome_id,
               o.match_id AS match_id,
               o.candidate_id AS candidate_id,
               o.config_keys AS config_keys,
               o.outcome AS outcome,
               o.value AS value
        ORDER BY o.created_at DESC
        LIMIT $limit
        """
        results = await self._driver.execute_query(
            cypher,
            parameters={
                "outcome_type": outcome_type,
                "tenant": self._db,
                "limit": limit * 5,  # Fetch extra for filtering
            },
            database=self._db,
        )

        total_outcomes = len(results)
        current_keys = self._extract_config_keys(current_config)

        # Count frequency of each config key set for probability correction
        config_freq: dict[str, int] = {}
        for record in results:
            config_key = ",".join(sorted(record.get("config_keys") or []))
            config_freq[config_key] = config_freq.get(config_key, 0) + 1

        matches: list[dict[str, Any]] = []

        for record in results:
            historical_keys = set(record.get("config_keys") or [])
            raw_sim = jaccard_similarity(current_keys, historical_keys)

            # Apply sample probability correction
            config_key = ",".join(sorted(record.get("config_keys") or []))
            frequency = config_freq.get(config_key, 1)
            similarity = corrected_similarity(raw_sim, frequency, total_outcomes)

            if similarity >= similarity_threshold:
                matches.append(
                    {
                        "outcome_id": record["outcome_id"],
                        "match_id": record["match_id"],
                        "candidate_id": record["candidate_id"],
                        "similarity": round(similarity, 4),
                        "raw_similarity": round(raw_sim, 4),
                        "outcome": record["outcome"],
                        "value": record["value"],
                    }
                )

            if len(matches) >= limit:
                break

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    async def detect_negative_patterns(
        self,
        current_config: dict[str, Any],
        similarity_threshold: float = 0.6,
    ) -> list[dict[str, Any]]:
        """Find configurations that historically resulted in failures."""
        return await self.find_similar_outcomes(
            current_config=current_config,
            outcome_type="failure",
            similarity_threshold=similarity_threshold,
            limit=5,
        )

    @staticmethod
    def _extract_config_keys(config: dict[str, Any]) -> set[str]:
        """Extract a flat set of configuration keys for similarity comparison."""
        keys: set[str] = set()
        for key, value in config.items():
            if isinstance(value, dict):
                for sub_key in value:
                    keys.add(f"{key}.{sub_key}")
            elif isinstance(value, list):
                keys.add(f"{key}[{len(value)}]")
            elif value is not None:
                keys.add(key)
        return keys
