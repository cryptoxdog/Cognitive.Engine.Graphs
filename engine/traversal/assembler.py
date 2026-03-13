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
import re

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)

# Dangerous Cypher keywords that must not appear in traversal patterns
_FORBIDDEN_KEYWORDS = frozenset(
    [
        "call",
        "with",
        "unwind",
        "return",
        "match",
        "foreach",
        "load",
        "using",
        "create",
        "merge",
        "delete",
        "remove",
        "set",
        "detach",
        "optional",
        "union",
        "apoc",
        "gds",
        "dbms",
    ]
)

# Valid traversal pattern regex:
# (alias:Label)-[:EDGE_TYPE*1..3]->(alias:Label)
# Allows optional labels, variable-length paths, bidirectional arrows
_TRAVERSAL_PATTERN_RE = re.compile(
    r"^\s*"
    r"\([a-zA-Z_][a-zA-Z0-9_]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?\)"  # (alias:Label)
    r"\s*<?-\s*"  # <- or -
    r"\[:[a-zA-Z_][a-zA-Z0-9_|]*(?:\*\d*(?:\.\.\d*)?)?\]"  # [:EDGE_TYPE*1..3]
    r"\s*-?>?\s*"  # -> or -
    r"\([a-zA-Z_][a-zA-Z0-9_]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?\)"  # (alias:Label)
    r"\s*$"
)


def _validate_traversal_pattern(pattern: str, step_name: str) -> str:
    """
    Validate traversal pattern for injection safety.

    Args:
        pattern: Cypher pattern from domain spec
        step_name: Name of the traversal step (for error messages)

    Returns:
        The validated pattern (unchanged if valid)

    Raises:
        ValueError: If pattern contains forbidden keywords or invalid syntax
    """
    # Check for forbidden keywords
    for keyword in _FORBIDDEN_KEYWORDS:
        keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
        if keyword_re.search(pattern):
            msg = f"Traversal step '{step_name}': forbidden keyword '{keyword}' in pattern"
            raise ValueError(msg)

    # Check for comment syntax
    if "//" in pattern or "/*" in pattern:
        msg = f"Traversal step '{step_name}': comment syntax forbidden in pattern"
        raise ValueError(msg)

    # Check for subquery braces (injection vector)
    if "{" in pattern or "}" in pattern:
        msg = f"Traversal step '{step_name}': subquery braces forbidden in pattern"
        raise ValueError(msg)

    # Check for parameter injection outside property access
    if re.search(r"\$[a-zA-Z_]", pattern):
        msg = f"Traversal step '{step_name}': parameter injection forbidden in pattern"
        raise ValueError(msg)

    # Validate pattern structure
    if not _TRAVERSAL_PATTERN_RE.match(pattern):
        msg = f"Traversal step '{step_name}': pattern does not match allowed structure"
        raise ValueError(msg)

    return pattern


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
        clauses: list[str] = []

        if self.traversal_spec is None:
            return clauses

        for step in self.traversal_spec.steps:
            # Check direction applicability
            if step.matchdirections and match_direction not in step.matchdirections:
                continue

            # Validate pattern for injection safety
            validated_pattern = _validate_traversal_pattern(step.pattern, step.name)

            # Build MATCH or OPTIONAL MATCH
            match_keyword = "MATCH" if step.required else "OPTIONAL MATCH"
            clause = f"{match_keyword} {validated_pattern}"

            clauses.append(clause)
            logger.debug(f"Added traversal step '{step.name}': {clause}")

        return clauses
