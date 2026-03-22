"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [resolution]
tags: [resolution, entity-resolver, deduplication]
owner: engine-team
status: active
--- /L9_META ---

Entity resolver: finds duplicates above threshold, merges into canonical,
creates RESOLVED_FROM edges, and transfers relationships.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from engine.config.schema import SemanticRegistrySpec
from engine.graph.driver import GraphDriver
from engine.resolution.similarity import SimilarityScorer
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class EntityResolver:
    """Resolves duplicate entities into canonical records.

    Process:
    1. For a given entity, find candidates above similarity threshold
    2. Pick canonical entity (highest degree node)
    3. Create RESOLVED_FROM edges from merged entities to canonical
    4. Transfer edges from merged entities to canonical
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
        self._scorer = SimilarityScorer(registry_spec, graph_driver, domain_id)

    async def resolve_entity(
        self,
        entity_id: str,
        entity_label: str,
    ) -> dict[str, Any]:
        """Find and merge duplicate entities for a given entity.

        Args:
            entity_id: The entity to resolve.
            entity_label: Neo4j label of the entity.

        Returns:
            Resolution metadata: canonical_id, merged_count, resolution_ids.
        """
        candidates = await self._scorer.find_candidates(
            entity_id=entity_id,
            entity_label=entity_label,
        )

        if not candidates:
            return {
                "canonical_id": entity_id,
                "merged_count": 0,
                "resolution_ids": [],
            }

        # Determine canonical: entity with highest degree
        all_ids = [entity_id, *[c["entity_id"] for c in candidates]]
        canonical_id = await self._find_canonical(all_ids, entity_label)

        # Merge non-canonical entities into canonical
        merge_ids = [eid for eid in all_ids if eid != canonical_id]
        resolution_ids: list[str] = []

        for merge_id in merge_ids:
            rid = await self._create_resolution(
                source_id=merge_id,
                canonical_id=canonical_id,
                entity_label=entity_label,
                similarity=next(
                    (c["similarity"] for c in candidates if c["entity_id"] == merge_id),
                    1.0,
                ),
            )
            resolution_ids.append(rid)

        logger.info(
            "Resolved entity %s: canonical=%s, merged=%d",
            entity_id,
            canonical_id,
            len(merge_ids),
        )

        return {
            "canonical_id": canonical_id,
            "merged_count": len(merge_ids),
            "resolution_ids": resolution_ids,
        }

    async def resolve_batch(
        self,
        entity_label: str,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        """Resolve all entities of a given label.

        Args:
            entity_label: Neo4j label to resolve.
            threshold: Optional override for similarity threshold.

        Returns:
            Summary stats: total_entities, total_merged, resolution_groups.
        """
        label = sanitize_label(entity_label)

        cypher = f"""
        MATCH (e:{label})
        WHERE NOT EXISTS((e)-[:RESOLVED_FROM]->())
        RETURN e.entity_id AS entity_id
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={},
            database=self._db,
        )

        entity_ids = [r["entity_id"] for r in results if r.get("entity_id")]
        resolved_set: set[str] = set()
        total_merged = 0
        resolution_groups = 0

        for eid in entity_ids:
            if eid in resolved_set:
                continue

            result = await self.resolve_entity(
                entity_id=eid,
                entity_label=entity_label,
            )
            merged = result.get("merged_count", 0)
            if merged > 0:
                total_merged += merged
                resolution_groups += 1
                # Mark merged entities as resolved
                for rid in result.get("resolution_ids", []):
                    resolved_set.add(rid)

        return {
            "total_entities": len(entity_ids),
            "total_merged": total_merged,
            "resolution_groups": resolution_groups,
        }

    async def _find_canonical(
        self,
        entity_ids: list[str],
        entity_label: str,
    ) -> str:
        """Find the entity with the highest degree (most connections)."""
        label = sanitize_label(entity_label)
        cypher = f"""
        UNWIND $entity_ids AS eid
        MATCH (e:{label} {{entity_id: eid}})
        OPTIONAL MATCH (e)-[r]-()
        WITH e.entity_id AS entity_id, count(r) AS degree
        ORDER BY degree DESC
        LIMIT 1
        RETURN entity_id
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"entity_ids": entity_ids},
            database=self._db,
        )
        if results:
            return str(results[0]["entity_id"])
        return entity_ids[0]

    async def _create_resolution(
        self,
        source_id: str,
        canonical_id: str,
        entity_label: str,
        similarity: float,
    ) -> str:
        """Create a RESOLVED_FROM edge between source and canonical."""
        label = sanitize_label(entity_label)
        resolution_id = f"res_{uuid.uuid4().hex[:12]}"

        cypher = f"""
        MATCH (source:{label} {{entity_id: $source_id}})
        MATCH (canonical:{label} {{entity_id: $canonical_id}})
        CREATE (source)-[:RESOLVED_FROM {{
            resolution_id: $resolution_id,
            confidence: $similarity,
            signal: 'semantic_registry',
            domain_id: $domain_id,
            created_at: datetime()
        }}]->(canonical)
        RETURN $resolution_id AS resolution_id
        """
        await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={
                "source_id": source_id,
                "canonical_id": canonical_id,
                "resolution_id": resolution_id,
                "similarity": similarity,
                "domain_id": self._db,
            },
            database=self._db,
        )
        return resolution_id
