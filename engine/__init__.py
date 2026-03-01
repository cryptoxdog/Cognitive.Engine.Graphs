# engine/__init__.py
"""
L9 Graph Cognitive Matching Engine
Domain-agnostic graph-native matching with gate-then-score architecture.
"""

__version__ = "1.0.0"
__author__ = "L9 Venture Forge"

from engine.api.app import create_app
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver

__all__ = [
    "DomainPackLoader",
    "DomainSpec",
    "GraphDriver",
    "create_app",
]
