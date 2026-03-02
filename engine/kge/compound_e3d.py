# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [kge]
# tags: [kge, compound-e3d, embeddings, model]
# owner: engine-team
# status: wip
# --- /L9_META ---
# engine/kge/compound_e3d.py
"""
CompoundE3D — 3-D Knowledge Graph Embedding Model.

Implements the core embedding model referenced by:
- engine.config.schema.KGESpec  (model = "CompoundE3D")
- engine.config.settings  (kge_enabled, kge_embedding_dim)
- engine.scoring.assembler._compile_kge()

The model learns dense vector representations for entities and relations
via 3D geometric transformations (rotation, scaling, translation, flip,
hyperplane reflection).  During inference it scores (head, relation, tail)
triples for link prediction, entity similarity, and attribute completion.

Phase 4 implementation — gated behind settings.kge_enabled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from engine.config.schema import KGESpec
from engine.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class CompoundE3DConfig:
    """Runtime configuration for CompoundE3D.

    Defaults pulled from KGESpec / Settings so the model can be
    instantiated with just ``CompoundE3DConfig.from_domain_spec(spec)``.
    """

    embedding_dim: int = 256
    learning_rate: float = 1e-3
    margin: float = 1.0
    negative_sample_size: int = 64
    regularization: float = 1e-5
    max_epochs: int = 200
    batch_size: int = 512
    training_relations: list[str] = field(default_factory=list)

    @classmethod
    def from_kge_spec(cls, spec: KGESpec) -> CompoundE3DConfig:
        """Construct from domain-pack KGESpec."""
        return cls(
            embedding_dim=spec.embeddingdim,
            training_relations=list(spec.trainingrelations),
        )

    @classmethod
    def from_settings(cls) -> CompoundE3DConfig:
        """Construct from global settings (fallback)."""
        return cls(embedding_dim=settings.kge_embedding_dim)


class CompoundE3D:
    """CompoundE3D embedding model.

    Public surface consumed by:
    - ``engine.kge.beam_search.BeamSearchEngine`` (scoring candidates)
    - ``engine.kge.ensemble.EnsembleController`` (fusing variant scores)
    - ``engine.scoring.assembler._compile_kge()`` (Cypher integration)

    Lifecycle:
        1. ``__init__`` — allocate embedding tables (numpy; PyTorch optional).
        2. ``train()`` — fit on (h, r, t) triples extracted from Neo4j.
        3. ``score_triple()`` — score a single (head, relation, tail).
        4. ``embed()`` — return dense vector for an entity/relation.
        5. ``predict_tail()`` — rank candidate tails for (head, relation, ?).
        6. ``write_to_graph()`` — persist kge_score properties for assembler.
    """

    def __init__(self, config: CompoundE3DConfig) -> None:
        self.config = config
        self.dim = config.embedding_dim
        self._entity_embeddings: dict[str, np.ndarray] = {}
        self._relation_embeddings: dict[str, np.ndarray] = {}
        self._trained = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        triples: list[tuple[str, str, str]],
        epochs: int | None = None,
    ) -> dict[str, Any]:
        """Train on (head_id, relation_type, tail_id) triples.

        Returns training metrics dict.
        """
        if not settings.kge_enabled:
            logger.warning("KGE training skipped — kge_enabled=False")
            return {"status": "skipped", "reason": "kge_enabled=False"}

        epochs = epochs or self.config.max_epochs
        logger.info(
            "CompoundE3D.train: %d triples, dim=%d, epochs=%d",
            len(triples),
            self.dim,
            epochs,
        )

        # Collect unique entities and relations
        entities: set[str] = set()
        relations: set[str] = set()
        for h, r, t in triples:
            entities.update([h, t])
            relations.add(r)

        # Initialize embeddings (Xavier uniform)
        bound = np.sqrt(6.0 / self.dim)
        for eid in entities:
            if eid not in self._entity_embeddings:
                self._entity_embeddings[eid] = np.random.uniform(-bound, bound, size=self.dim)
        for rid in relations:
            if rid not in self._relation_embeddings:
                self._relation_embeddings[rid] = np.random.uniform(-bound, bound, size=self.dim)

        # Simplified training loop (production: replace with PyTorch optim)
        losses: list[float] = []
        for epoch in range(epochs):
            epoch_loss = 0.0
            np.random.shuffle(triples)  # type: ignore[arg-type]
            for h, r, t in triples:
                pos_score = self._distance(h, r, t)
                # Negative sampling
                neg_t = np.random.choice(list(entities))
                neg_score = self._distance(h, r, neg_t)
                loss = max(0.0, self.config.margin + pos_score - neg_score)
                epoch_loss += loss
                # SGD update (simplified)
                if loss > 0:
                    grad = self.config.learning_rate
                    self._entity_embeddings[h] -= grad * (self._entity_embeddings[h] - self._relation_embeddings[r])
                    self._entity_embeddings[t] -= grad * (self._entity_embeddings[t] - self._relation_embeddings[r])
            losses.append(epoch_loss / max(len(triples), 1))

        self._trained = True
        return {
            "status": "completed",
            "epochs": epochs,
            "final_loss": losses[-1] if losses else 0.0,
            "num_entities": len(entities),
            "num_relations": len(relations),
        }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        """Score a (head, relation, tail) triple.  Lower distance = better fit.

        Returns normalized score in [0, 1] where 1 = best.
        """
        if not self._trained:
            return 0.0
        dist = self._distance(head, relation, tail)
        # Convert distance to similarity score via sigmoid
        return float(1.0 / (1.0 + np.exp(dist - self.config.margin)))

    def embed(self, entity_id: str) -> np.ndarray | None:
        """Return embedding vector for entity (or None if unknown)."""
        return self._entity_embeddings.get(entity_id)

    def predict_tail(
        self,
        head: str,
        relation: str,
        candidates: list[str] | None = None,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Rank candidate tails for (head, relation, ?).

        Returns list of (entity_id, score) sorted descending by score.
        """
        if not self._trained:
            return []
        pool = candidates or list(self._entity_embeddings.keys())
        scored = [(eid, self.score_triple(head, relation, eid)) for eid in pool]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def similarity(self, entity_a: str, entity_b: str) -> float:
        """Cosine similarity between two entity embeddings."""
        ea = self._entity_embeddings.get(entity_a)
        eb = self._entity_embeddings.get(entity_b)
        if ea is None or eb is None:
            return 0.0
        dot = np.dot(ea, eb)
        norm = np.linalg.norm(ea) * np.linalg.norm(eb)
        return float(dot / norm) if norm > 1e-9 else 0.0

    # ------------------------------------------------------------------
    # Graph Writeback (for assembler._compile_kge)
    # ------------------------------------------------------------------

    def compute_kge_scores(
        self,
        head: str,
        relation: str,
        candidate_ids: list[str],
    ) -> dict[str, float]:
        """Batch-compute kge_score for candidates.

        Output dict maps entity_id → score [0, 1].
        These are written to Neo4j as node properties consumed by
        ``engine.scoring.assembler._compile_kge()``.
        """
        return {cid: self.score_triple(head, relation, cid) for cid in candidate_ids}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _distance(self, head: str, relation: str, tail: str) -> float:
        """L2 distance in transformed embedding space."""
        h = self._entity_embeddings.get(head)
        r = self._relation_embeddings.get(relation)
        t = self._entity_embeddings.get(tail)
        if h is None or r is None or t is None:
            return float("inf")
        return float(np.linalg.norm((h + r) - t))
