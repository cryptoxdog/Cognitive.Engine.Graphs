"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [utils]
tags: [structlog, observability]
owner: engine-team
status: active
--- /L9_META ---

engine/utils/logger.py

Engine-side logger accessor only.

Per L9 contracts, global logging configuration belongs to the chassis/runtime
layer, not engine/. This module only returns a logger handle.
"""
from __future__ import annotations

import structlog


def get_logger(name: str = "engine"):
    """Return a bound structlog logger without configuring global logging."""
    return structlog.get_logger(name)
