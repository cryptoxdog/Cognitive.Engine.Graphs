"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [resolution]
tags: [resolution, similarity, jaccard, structural]
owner: engine-team
status: active
--- /L9_META ---

Multi-signal entity similarity scoring.
Combines property (Jaccard), structural (neighbor overlap),
and behavioral (outcome pattern) signals inspired by OmniSage.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import SemanticRegistrySpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class SimilarityScorer:
    """Multi-signal entity similarity scorer.

    Three similarity signals combined:
    1. Property similarity (entity-feature): Jaccard for categorical properties
    2. Structural similarity (entity-entity): shared neighbor count
    3. Behavioral similarity (user-entity): shared TransactionOutcome patterns

    Final score = alpha * property_sim + beta * structural_sim + gamma * behavioral_sim
    """

    def __init__(
        self,
        registry_spec: SemanticRegistrySpec,
        graph_driver: GraphDriver,
        domain_id: str,
    ) -> None:
        self._spec = registry_spec
        self._graph_driver = graph_driver
        self._db = domain_id

    async def compute_similarity(
        self,
        entity_a_id: str,
        entity_b_id: str,
        entity_label: str,
    ) -> float:
        """Compute weighted multi-signal similarity between two entities.

        Args:
            entity_a_id: First entity ID.
            entity_b_id: Second entity ID.
            entity_label: The Neo4j label of both entities.

        Returns:
            Weighted similarity score in [0, 1].
        """
        label = sanitize_label(entity_label)

        property_sim = await self._property_similarity(entity_a_id, entity_b_id, label)
        structural_sim = await self._structural_similarity(entity_a_id, entity_b_id, label)
        behavioral_sim = await self._behavioral_similarity(entity_a_id, entity_b_id)

        score = (
            self._spec.property_weight * property_sim
            + self._spec.structural_weight * structural_sim
            + self._spec.behavioral_weight * behavioral_sim
        )
        return min(1.0, max(0.0, score))

    async def find_candidates(
        self,
        entity_id: str,
        entity_label: str,
        threshold: float | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Find entities similar to the given entity.

        Uses property comparison as initial candidate filter,
        then computes full multi-signal similarity.

        Args:
            entity_id: The entity to find matches for.
            entity_label: Neo4j label of the entity.
            threshold: Minimum similarity score (defaults to spec threshold).
            limit: Max candidates to return (defaults to spec max_candidates).

        Returns:
            List of dicts with entity_id and similarity score.
        """
        effective_threshold = threshold if threshold is not None else self._spec.similarity_threshold
        effective_limit = limit if limit is not None else self._spec.max_candidates
        label = sanitize_label(entity_label)

        # Phase 1: find candidate pairs via property overlap
        candidate_ids = await self._find_property_candidates(entity_id, label, effective_limit)

        # Phase 2: compute full similarity for each candidate
        results: list[dict[str, Any]] = []
        for cid in candidate_ids:
            if cid == entity_id:
                continue
            sim = await self.compute_similarity(entity_id, cid, entity_label)
            if sim >= effective_threshold:
                results.append({"entity_id": cid, "similarity": round(sim, 4)})

        results.sort(key=lambda x: -x["similarity"])
        return results[:effective_limit]

    async def _property_similarity(
        self,
        entity_a_id: str,
        entity_b_id: str,
        label: str,
    ) -> float:
        """Jaccard similarity over comparison properties."""
        comp_props = self._spec.comparison_properties
        if not comp_props:
            return 0.0

        safe_props = [sanitize_label(p) for p in comp_props]
        return_clauses = ", ".join(f"a.{p} AS a_{p}, b.{p} AS b_{p}" for p in safe_props)

        cypher = f"""
        MATCH (a:{label} {{entity_id: $a_id}})
        MATCH (b:{label} {{entity_id: $b_id}})
        RETURN {return_clauses}
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"a_id": entity_a_id, "b_id": entity_b_id},
            database=self._db,
        )
        if not results:
            return 0.0

        row = results[0]
        matches = 0
        total = 0
        for p in safe_props:
            val_a = row.get(f"a_{p}")
            val_b = row.get(f"b_{p}")
            if val_a is not None and val_b is not None:
                total += 1
                if val_a == val_b:
                    matches += 1

        return matches / total if total > 0 else 0.0

    async def _structural_similarity(
        self,
        entity_a_id: str,
        entity_b_id: str,
        label: str,
    ) -> float:
        """Shared neighbor overlap (Jaccard on neighbor sets)."""
        cypher = f"""
        MATCH (a:{label} {{entity_id: $a_id}})--(neighbor_a)
        WITH a, collect(DISTINCT id(neighbor_a)) AS neighbors_a
        MATCH (b:{label} {{entity_id: $b_id}})--(neighbor_b)
        WITH neighbors_a, collect(DISTINCT id(neighbor_b)) AS neighbors_b
        WITH neighbors_a, neighbors_b,
             [x IN neighbors_a WHERE x IN neighbors_b] AS shared
        RETURN size(shared) AS shared_count,
               size(neighbors_a) + size(neighbors_b) - size(shared) AS union_count
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"a_id": entity_a_id, "b_id": entity_b_id},
            database=self._db,
        )
        if not results:
            return 0.0
        row = results[0]
        shared = row.get("shared_count", 0)
        union = row.get("union_count", 0)
        return shared / union if union > 0 else 0.0

    async def _behavioral_similarity(
        self,
        entity_a_id: str,
        entity_b_id: str,
    ) -> float:
        """Shared TransactionOutcome pattern similarity."""
        cypher = """
        OPTIONAL MATCH (a {entity_id: $a_id})-[:RESULTED_IN]->(oa:TransactionOutcome)
        WITH collect(DISTINCT oa.match_id) AS matches_a
        OPTIONAL MATCH (b {entity_id: $b_id})-[:RESULTED_IN]->(ob:TransactionOutcome)
        WITH matches_a, collect(DISTINCT ob.match_id) AS matches_b
        WITH matches_a, matches_b,
             [x IN matches_a WHERE x IN matches_b] AS shared
        RETURN size(shared) AS shared_count,
               size(matches_a) + size(matches_b) - size(shared) AS union_count
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"a_id": entity_a_id, "b_id": entity_b_id},
            database=self._db,
        )
        if not results:
            return 0.0
        row = results[0]
        shared = row.get("shared_count", 0)
        union = row.get("union_count", 0)
        return shared / union if union > 0 else 0.0

    async def _find_property_candidates(
        self,
        entity_id: str,
        label: str,
        limit: int,
    ) -> list[str]:
        """Find candidate entity IDs that share property values."""
        comp_props = self._spec.comparison_properties
        if not comp_props:
            # Fallback: return all entities of the same label
            cypher = f"""
            MATCH (e:{label})
            WHERE e.entity_id <> $entity_id
            RETURN e.entity_id AS entity_id
            LIMIT $limit
            """
            results = await self._graph_driver.execute_query(
                cypher=cypher,
                parameters={"entity_id": entity_id, "limit": limit},
                database=self._db,
            )
            return [r["entity_id"] for r in results if r.get("entity_id")]

        # Match entities that share at least one comparison property value
        safe_prop = sanitize_label(comp_props[0])
        cypher = f"""
        MATCH (source:{label} {{entity_id: $entity_id}})
        MATCH (candidate:{label})
        WHERE candidate.entity_id <> $entity_id
              AND candidate.{safe_prop} = source.{safe_prop}
        RETURN candidate.entity_id AS entity_id
        LIMIT $limit
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"entity_id": entity_id, "limit": limit},
            database=self._db,
        )
        return [r["entity_id"] for r in results if r.get("entity_id")]
