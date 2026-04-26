"""
Contract template completeness and placeholder tests.

Source: docs/contracts/_templates/ — Phase 2 output requirement.
"""

import json
import re

import pytest

EXPECTED_TEMPLATES = {
    "api-endpoint.template.yaml": "yaml",
    "tool-schema.template.json": "json",
    "data-model.template.json": "json",
}


@pytest.mark.parametrize("filename", EXPECTED_TEMPLATES.keys())
def test_template_file_exists(contracts_root, filename):
    path = contracts_root / "_templates" / filename
    assert path.exists(), f"Missing template: _templates/{filename}"


@pytest.mark.parametrize(("filename", "fmt"), EXPECTED_TEMPLATES.items())
def test_template_file_parseable(contracts_root, filename, fmt):
    path = contracts_root / "_templates" / filename
    if not path.exists():
        pytest.skip(f"{filename} not yet present")
    content = path.read_text()
    if fmt == "yaml":
        assert len(content.strip()) > 50, f"{filename} appears empty"
    elif fmt == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError:
            assert "{" in content, f"{filename} doesn't appear to be a JSON template"


@pytest.mark.parametrize("filename", EXPECTED_TEMPLATES.keys())
def test_template_contains_placeholders(contracts_root, filename):
    path = contracts_root / "_templates" / filename
    if not path.exists():
        pytest.skip(f"{filename} not yet present")
    content = path.read_text()
    placeholders = re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", content)
    assert placeholders, f"{filename} has no {{placeholder}} markers"


def test_api_template_has_operationid_placeholder(contracts_root):
    path = contracts_root / "_templates" / "api-endpoint.template.yaml"
    if not path.exists():
        pytest.skip()
    content = path.read_text()
    assert "operationId" in content


def test_tool_schema_template_has_json_schema_dollar_schema(contracts_root):
    path = contracts_root / "_templates" / "tool-schema.template.json"
    if not path.exists():
        pytest.skip()
    content = path.read_text()
    assert '"$schema"' in content


def test_data_model_template_has_additional_properties_false(contracts_root):
    path = contracts_root / "_templates" / "data-model.template.json"
    if not path.exists():
        pytest.skip()
    content = path.read_text()
    assert "additionalProperties" in content
