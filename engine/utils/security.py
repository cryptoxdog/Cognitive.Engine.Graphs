"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [utils, security, sanitize]
owner: engine-team
status: active
--- /L9_META ---

engine/utils/security.py
Security utilities for the L9 Graph Cognitive Engine.
"""
from __future__ import annotations

import re


def sanitize_label(label: str) -> str:
    """
    Validate Neo4j label/relationship type to prevent Cypher injection.
    
    SECURITY: Labels are interpolated into Cypher queries. User-uploaded
    domain specs could contain malicious labels with injection payloads.
    
    Valid labels: [A-Za-z_][A-Za-z0-9_]*
    
    Raises ValueError if invalid.
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', label):
        raise ValueError(f"Invalid label or type: {label!r}")
    return label
