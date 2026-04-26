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

_MAX_LABEL_LEN = 64


def sanitize_label(label: str) -> str:
    """
    Validate Neo4j label/relationship type to prevent Cypher injection.

    SECURITY: Labels are interpolated into Cypher queries. User-uploaded
    domain specs could contain malicious labels with injection payloads.

    Valid labels: [A-Za-z_][A-Za-z0-9_]*, max 64 characters.

    Raises ValueError if invalid.
    """
    if len(label) > _MAX_LABEL_LEN:
        msg = f"Label exceeds maximum length of {_MAX_LABEL_LEN}: {label!r}"
        raise ValueError(msg)
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", label):
        msg = f"Invalid label or type: {label!r}"
        raise ValueError(msg)
    return label
