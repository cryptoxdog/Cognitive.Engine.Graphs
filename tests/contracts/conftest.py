"""
Shared fixtures for contract validation tests.

Constants live in _constants.py (directly importable).
This file provides pytest fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.contracts._constants import CONTRACTS_ROOT


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture
def contracts_root() -> Path:
    return CONTRACTS_ROOT


@pytest.fixture
def openapi_spec() -> dict:
    path = CONTRACTS_ROOT / "api" / "openapi.yaml"
    if not path.exists():
        pytest.skip("openapi.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def env_contract() -> dict:
    path = CONTRACTS_ROOT / "config" / "env-contract.yaml"
    if not path.exists():
        pytest.skip("env-contract.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def graph_schema() -> dict:
    path = CONTRACTS_ROOT / "data" / "graph-schema.yaml"
    if not path.exists():
        pytest.skip("graph-schema.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def asyncapi_spec() -> dict:
    path = CONTRACTS_ROOT / "events" / "asyncapi.yaml"
    if not path.exists():
        pytest.skip("asyncapi.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def neo4j_dep() -> dict:
    path = CONTRACTS_ROOT / "dependencies" / "neo4j.yaml"
    if not path.exists():
        pytest.skip("neo4j.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def redis_dep() -> dict:
    path = CONTRACTS_ROOT / "dependencies" / "redis.yaml"
    if not path.exists():
        pytest.skip("redis.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def tool_index() -> dict:
    path = CONTRACTS_ROOT / "agents" / "tool-schemas" / "_index.yaml"
    if not path.exists():
        pytest.skip("_index.yaml not present")
    return _load_yaml(path)


@pytest.fixture
def outcome_record_schema() -> dict:
    path = CONTRACTS_ROOT / "data" / "models" / "outcome-record.schema.json"
    if not path.exists():
        pytest.skip("outcome-record.schema.json not present")
    return _load_json(path)


@pytest.fixture
def packet_envelope_schema() -> dict:
    path = CONTRACTS_ROOT / "data" / "models" / "packet-envelope.schema.json"
    if not path.exists():
        pytest.skip("packet-envelope.schema.json not present")
    return _load_json(path)
