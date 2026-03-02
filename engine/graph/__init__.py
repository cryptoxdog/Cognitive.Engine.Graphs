"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [graph, driver]
owner: engine-team
status: active
--- /L9_META ---

Graph database interface."""
from engine.graph.driver import GraphDriver

__all__ = ["GraphDriver"]


