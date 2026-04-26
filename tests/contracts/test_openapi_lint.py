"""
Structural OpenAPI spec linting using openapi-spec-validator.

Source: Phase 4.3 — validation commands.
"""

import pytest

try:
    from openapi_spec_validator import validate
    from openapi_spec_validator.readers import read_from_filename

    HAS_VALIDATOR = True
except ImportError:
    HAS_VALIDATOR = False


@pytest.mark.skipif(not HAS_VALIDATOR, reason="openapi-spec-validator not installed")
def test_openapi_spec_passes_lint(contracts_root):
    spec_path = contracts_root / "api" / "openapi.yaml"
    if not spec_path.exists():
        pytest.skip("openapi.yaml not yet generated")
    spec_dict, _ = read_from_filename(str(spec_path))
    validate(spec_dict)


@pytest.mark.skipif(not HAS_VALIDATOR, reason="openapi-spec-validator not installed")
def test_openapi_all_refs_resolve(contracts_root):
    spec_path = contracts_root / "api" / "openapi.yaml"
    if not spec_path.exists():
        pytest.skip("openapi.yaml not yet generated")
    spec_dict, _ = read_from_filename(str(spec_path))
    validate(spec_dict)
