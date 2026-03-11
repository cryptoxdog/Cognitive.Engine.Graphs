"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [engine-core]
owner: engine-team
status: active
--- /L9_META ---

L9 Graph Cognitive Matching Engine
Domain-agnostic graph-native matching with gate-then-score architecture.

Chassis Integration:
  from engine.handlers import register_all, init_dependencies
  init_dependencies(graph_driver, domain_loader)
  register_all(chassis.router)
"""

__version__ = "1.1.0"
__author__ = "L9 Venture Forge"

from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies, register_all

__all__ = [
    "DomainPackLoader",
    "DomainSpec",
    "GraphDriver",
    "init_dependencies",
    "register_all",
]
