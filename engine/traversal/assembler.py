"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [traversal, assembler, cypher]
owner: engine-team
status: active
--- /L9_META ---

Traversal assembler: steps → MATCH/OPTIONAL MATCH ordering.
Compiles declarative traversal steps into Cypher MATCH clauses.
"""

import logging

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)


class TraversalAssembler:
    """Assembles traversal steps into Cypher MATCH clauses."""

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec
        self.traversal_spec = domain_spec.traversal

    def assemble_traversal(self, match_direction: str) -> list[str]:
        """
        Assemble MATCH clauses for traversal steps.

        Args:
            match_direction: Current match direction

        Returns:
            List of Cypher MATCH clauses
        """
        clauses = []

        for step in self.traversal_spec.steps:
            # Check direction applicability
            if step.matchdirections and match_direction not in step.matchdirections:
                continue

            # Build MATCH or OPTIONAL MATCH
            match_keyword = "MATCH" if step.required else "OPTIONAL MATCH"
            clause = f"{match_keyword} {step.pattern}"

            clauses.append(clause)
            logger.debug(f"Added traversal step '{step.name}': {clause}")

        return clauses
