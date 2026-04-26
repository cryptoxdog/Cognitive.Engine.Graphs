"""
Agent tool schema contract tests.

Sources:
  engine/handlers.py — handle_match, handle_sync, handle_admin,
                       handle_outcomes, handle_resolve, handle_enrich
  engine/auth/capabilities.py — ACTION_PERMISSION_MAP
  docs/contracts/agents/tool-schemas/_index.yaml
"""

import json

import pytest

from tests.contracts._constants import ACTION_PERMISSION_MAP

TOOL_NAMES = {"match", "sync", "admin", "outcomes", "resolve", "enrich"}


def get_tool_schema(contracts_root, name):
    p = contracts_root / "agents" / "tool-schemas" / f"{name}.schema.json"
    if not p.exists():
        pytest.xfail(f"tool schema {name}.schema.json not yet generated")
    return json.loads(p.read_text())


# ── Index ────────────────────────────────────────────────────────────────────


def test_tool_index_exists(tool_index):
    assert "tools" in tool_index


def test_tool_index_covers_all_engine_tools(tool_index):
    declared = {t["name"] for t in tool_index.get("tools", [])}
    missing = TOOL_NAMES - declared
    assert not missing, f"_index.yaml missing tool entries: {missing}"


def test_tool_index_entries_have_required_fields(tool_index):
    for t in tool_index.get("tools", []):
        assert "name" in t
        assert "schema_file" in t, f"Tool '{t.get('name')}' missing schema_file"
        assert "capability" in t, f"Tool '{t.get('name')}' missing capability"


def test_tool_index_capabilities_match_permission_map(tool_index):
    for t in tool_index.get("tools", []):
        name = t.get("name")
        if name not in ACTION_PERMISSION_MAP:
            continue
        expected = ACTION_PERMISSION_MAP[name]
        actual = t.get("capability")
        assert actual == expected, f"Tool '{name}' capability mismatch: contract={actual}, source={expected}"


# ── Per-schema structural rules ──────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_dollar_schema(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert "$schema" in schema, f"{name}.schema.json missing $schema"


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_title(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert schema.get("title"), f"{name}.schema.json missing title"


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_description(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert schema.get("description"), f"{name}.schema.json missing description"


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_is_object_type(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert schema.get("type") == "object"


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_examples(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert schema.get("examples"), f"{name}.schema.json missing examples"


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_additional_properties_false(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    assert schema.get("additionalProperties") is False


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_tool_schema_has_source_ref(contracts_root, name):
    schema = get_tool_schema(contracts_root, name)
    desc = schema.get("description", "")
    assert "engine/handlers.py" in desc or "x-source-file" in str(schema)
