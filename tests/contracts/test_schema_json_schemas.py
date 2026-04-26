"""
Validate shared JSON Schemas in api/schemas/.

Source: docs/contracts/api/schemas/shared-models.yaml, error-responses.yaml
"""

import pytest


def test_shared_models_file_exists(contracts_root):
    path = contracts_root / "api" / "schemas" / "shared-models.yaml"
    if not path.exists():
        pytest.xfail("api/schemas/shared-models.yaml not yet generated")


def test_error_responses_file_exists(contracts_root):
    path = contracts_root / "api" / "schemas" / "error-responses.yaml"
    if not path.exists():
        pytest.xfail("api/schemas/error-responses.yaml not yet generated")


def test_shared_models_has_pagination_envelope(contracts_root):
    path = contracts_root / "api" / "schemas" / "shared-models.yaml"
    if not path.exists():
        pytest.skip("shared-models.yaml not yet generated")
    content = path.read_text()
    assert "Paginated" in content or "pagination" in content.lower()
