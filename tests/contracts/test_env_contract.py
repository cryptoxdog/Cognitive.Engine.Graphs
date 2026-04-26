"""
Environment variable contract tests.

Sources:
  engine/config/settings.py:Settings — all env var declarations
  chassis/app.py:ChassisSettings
  docker-compose.yml
"""

from tests.contracts._constants import FORBIDDEN_PROD_SECRETS, REQUIRED_ENV_VARS

# ── 1. Schema structure ─────────────────────────────────────────────────────


def test_env_contract_has_variables_key(env_contract):
    assert "variables" in env_contract, "env-contract.yaml must have a top-level 'variables' list"


def test_env_contract_is_list(env_contract):
    assert isinstance(env_contract.get("variables"), list)


# ── 2. Every variable entry must have required fields ────────────────────────


def test_every_variable_has_name(env_contract):
    for i, var in enumerate(env_contract["variables"]):
        assert "name" in var, f"variables[{i}] missing 'name' field"


def test_every_variable_has_type(env_contract):
    for var in env_contract["variables"]:
        assert "type" in var, f"Variable '{var.get('name', '?')}' missing 'type'"


def test_every_variable_has_description(env_contract):
    for var in env_contract["variables"]:
        assert var.get("description"), f"Variable '{var.get('name', '?')}' missing description"


def test_every_variable_has_required_field(env_contract):
    for var in env_contract["variables"]:
        assert "required" in var, f"Variable '{var.get('name', '?')}' missing 'required' boolean"


def test_every_variable_has_source(env_contract):
    for var in env_contract["variables"]:
        assert "source" in var, f"Variable '{var.get('name', '?')}' missing 'source' field"


# ── 3. Required variables are covered ────────────────────────────────────────


def test_all_required_env_vars_declared(env_contract):
    declared_names = {v["name"] for v in env_contract["variables"]}
    for var_name in REQUIRED_ENV_VARS:
        assert var_name in declared_names, f"Required env var '{var_name}' not declared"


def test_required_vars_are_marked_required(env_contract):
    by_name = {v["name"]: v for v in env_contract["variables"]}
    for var_name in REQUIRED_ENV_VARS:
        if var_name in by_name:
            assert by_name[var_name].get("required") is True, (
                f"'{var_name}' is required in settings.py but marked required=false"
            )


# ── 4. Secret safety — production guards ────────────────────────────────────


def test_sensitive_secrets_marked_sensitive(env_contract):
    by_name = {v["name"]: v for v in env_contract["variables"]}
    for secret_name in ("NEO4J_PASSWORD", "API_KEY"):
        if secret_name in by_name:
            assert by_name[secret_name].get("sensitive") is True, f"'{secret_name}' must be marked sensitive: true"


def test_secret_defaults_are_documented_as_unsafe(env_contract):
    by_name = {v["name"]: v for v in env_contract["variables"]}
    for secret_name, unsafe_defaults in FORBIDDEN_PROD_SECRETS.items():
        if secret_name not in by_name:
            continue
        entry = by_name[secret_name]
        default = str(entry.get("default", ""))
        desc = entry.get("description", "")
        if default in unsafe_defaults:
            assert "prod" in desc.lower() or "production" in desc.lower() or "change" in desc.lower(), (
                f"'{secret_name}' has unsafe default '{default}' but description doesn't warn about production"
            )


# ── 5. Circuit breaker config coverage ──────────────────────────────────────

CIRCUIT_BREAKER_VARS = [
    "NEO4J_CIRCUIT_THRESHOLD",
    "NEO4J_CIRCUIT_COOLDOWN",
    "NEO4J_CIRCUIT_HALF_OPEN_MAX",
]


def test_circuit_breaker_vars_declared(env_contract):
    declared = {v["name"] for v in env_contract["variables"]}
    for var in CIRCUIT_BREAKER_VARS:
        assert var in declared, f"Circuit breaker env var '{var}' not in env-contract.yaml"


def test_neo4j_circuit_threshold_default_is_5(env_contract):
    by_name = {v["name"]: v for v in env_contract["variables"]}
    entry = by_name.get("NEO4J_CIRCUIT_THRESHOLD")
    if entry:
        assert entry.get("default") == 5, "NEO4J_CIRCUIT_THRESHOLD default must be 5"


# ── 6. Scoring weight coverage ──────────────────────────────────────────────

SCORING_WEIGHT_VARS = ["W_STRUCTURAL", "W_GEO", "W_REINFORCEMENT", "W_FRESHNESS"]


def test_scoring_weight_vars_declared(env_contract):
    declared = {v["name"] for v in env_contract["variables"]}
    for var in SCORING_WEIGHT_VARS:
        assert var in declared, f"Scoring weight var '{var}' not in env-contract.yaml"


def test_scoring_weights_have_range_validation(env_contract):
    by_name = {v["name"]: v for v in env_contract["variables"]}
    for var in SCORING_WEIGHT_VARS:
        if var in by_name:
            validation = by_name[var].get("validation", "")
            val_str = str(validation)
            assert "0.0" in val_str, f"'{var}' must have range validation minimum 0.0"
            assert "1.0" in val_str, f"'{var}' must have range validation maximum 1.0"
