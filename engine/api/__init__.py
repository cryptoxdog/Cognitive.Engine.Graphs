# engine/api/__init__.py
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [api]
tags: [api, fastapi, chassis]
owner: engine-team
status: active
--- /L9_META ---

API module for L9 Graph Cognitive Engine.
Provides FastAPI app factory for chassis integration.
"""

from engine.api.app import app, create_app

__all__ = ["app", "create_app"]
