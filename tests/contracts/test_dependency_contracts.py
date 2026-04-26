"""
External dependency contract tests for Neo4j and Redis.

Sources:
  engine/graph/driver.py:GraphDriver, CircuitBreaker
  docker-compose.yml
  engine/config/settings.py
"""


# ── Neo4j dependency contract ────────────────────────────────────────────────


def test_neo4j_dep_service_name(neo4j_dep):
    assert neo4j_dep.get("service_name") == "neo4j"


def test_neo4j_dep_version_is_5_enterprise(neo4j_dep):
    version = str(neo4j_dep.get("version", ""))
    assert "5" in version
    assert "enterprise" in version.lower()


def test_neo4j_dep_has_plugins(neo4j_dep):
    plugins = [p.lower() for p in neo4j_dep.get("plugins", [])]
    assert "apoc" in plugins
    assert "graph-data-science" in plugins


def test_neo4j_dep_connection_uses_env_vars(neo4j_dep):
    conn = neo4j_dep.get("connection", {})
    assert conn.get("base_url_env") == "NEO4J_URI"
    assert conn.get("username_env") == "NEO4J_USERNAME"
    assert conn.get("password_env") == "NEO4J_PASSWORD"


def test_neo4j_dep_has_circuit_breaker(neo4j_dep):
    cb = neo4j_dep.get("circuit_breaker", {})
    assert cb.get("enabled") is True


def test_neo4j_dep_circuit_breaker_references_source(neo4j_dep):
    cb = neo4j_dep.get("circuit_breaker", {})
    impl = cb.get("implementation", "")
    assert "circuit_breaker" in impl or "CircuitBreaker" in impl


def test_neo4j_dep_circuit_breaker_has_error_type(neo4j_dep):
    cb = neo4j_dep.get("circuit_breaker", {})
    assert "error_on_open" in cb


def test_neo4j_dep_has_health_check(neo4j_dep):
    hc = neo4j_dep.get("health_check", {})
    assert hc.get("query")
    assert "ping" in hc["query"].lower() or "return" in hc["query"].lower()


def test_neo4j_dep_direct_access_forbidden(neo4j_dep):
    qi = neo4j_dep.get("query_interface", {})
    direct = str(qi.get("direct_access", "")).lower()
    assert direct == "forbidden"


# ── Redis dependency contract ────────────────────────────────────────────────


def test_redis_dep_service_name(redis_dep):
    assert redis_dep.get("service_name") == "redis"


def test_redis_dep_version_is_7(redis_dep):
    version = str(redis_dep.get("version", ""))
    assert "7" in version


def test_redis_dep_uses_env_var(redis_dep):
    conn = redis_dep.get("connection", {})
    assert conn.get("base_url_env") == "REDIS_URL"


def test_redis_dep_usage_documents_scoring_cache(redis_dep):
    usages = [u.get("purpose", "").lower() for u in redis_dep.get("usage", [])]
    scoring_cached = any("scor" in u or "cache" in u or "gds" in u for u in usages)
    assert scoring_cached
