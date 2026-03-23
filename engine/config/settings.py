"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [config, settings]
owner: engine-team
status: active
--- /L9_META ---

engine/config/settings.py

Application settings via pydantic-settings.
Reads from .env file and environment variables.
Single source of truth for all L9_* configuration.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRETS = frozenset({"password", "change-me-in-production"})


class Settings(BaseSettings):
    """L9 Engine configuration. All env vars prefixed L9_ unless noted."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Project Identity ---
    l9_project: str = "l9-engine"
    l9_env: str = "dev"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"
    neo4j_pool_size: int = 50
    neo4j_max_connection_lifetime: int = 3600
    neo4j_connection_acquisition_timeout: int = 60

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- API ---
    api_port: int = 8000
    api_workers: int = 4
    api_secret_key: str = "change-me-in-production"
    cors_origins: list[str] = []  # Default deny-all; set via CORS_ORIGINS env var

    # --- Domain Packs ---
    domains_root: Path = Path("./domains")

    # --- Logging ---
    log_level: str = "INFO"

    # --- GDS ---
    gds_enabled: bool = True

    # --- Scoring Weights (defaults, overridable per-request) ---
    w_structural: float = 0.30
    w_geo: float = 0.25
    w_reinforcement: float = 0.20
    w_freshness: float = 0.10
    geo_decay_km: float = 800.0
    community_cross_bias: float = 0.92
    max_results: int = 25

    # --- Temporal Decay ---
    decay_transaction_halflife: float = 180.0  # days
    decay_facility_halflife: float = 90.0
    decay_structural_halflife: float = 365.0

    # --- Feedback Loop ---
    outcome_ema_alpha: float = 0.1

    # --- Entity Resolution ---
    resolution_density_tolerance: float = 0.05
    resolution_mfi_tolerance: float = 5.0
    resolution_min_confidence: float = 0.6

    # --- KGE (Phase 4) ---
    kge_enabled: bool = False
    kge_embedding_dim: int = 256  # Must match KGESpec.embeddingdim default (schema.py)
    kge_confidence_threshold: float = 0.3

    # --- Pareto / Multi-Objective ---
    pareto_enabled: bool = True
    pareto_n_samples: int = 50
    pareto_weight_discovery_enabled: bool = False  # off until outcome data flows

    # --- Wave 1: Invariant & Validation Hardening (seL4-inspired) ---
    domain_strict_validation: bool = True  # W1-01: cross-reference validators at load time
    score_clamp_enabled: bool = True  # W1-02: clamp dimension scores to [0, 1]
    strict_null_gates: bool = True  # W1-03: reject gates with null-resolved params
    max_hop_hard_cap: int = 10  # W1-04: maximum hops for traversal patterns
    param_strict_mode: bool = True  # W1-05: raise on derived parameter resolution failures

    # --- Wave 2: Refinement-Inspired Scoring ---
    feedback_enabled: bool = False  # W2-02: outcome feedback loop (opt-in)
    confidence_check_enabled: bool = True  # W2-03: ensemble confidence bounds
    monoculture_threshold: float = 0.70  # W2-03: single-dimension dominance cap
    ensemble_max_divergence: float = 0.30  # W2-03: GDS/KGE divergence cap (Wave 6)
    score_normalize: bool = False  # W2-04: post-query min-max normalization (opt-in)

    # --- Wave 3: Capability & Access Control (seL4-inspired) ---
    tenant_auth_enabled: bool = True  # W3-01: JWT allowed_tenants enforcement
    tenant_auth_bypass_key: str = ""  # W3-01: service-to-service bypass key
    capability_auth_enabled: bool = True  # W3-02/W3-03: domain-spec capability model

    # --- Wave 4: State Management & Resilience (seL4-inspired) ---
    neo4j_circuit_threshold: int = 5  # W4-02: consecutive failures before circuit opens
    neo4j_circuit_cooldown: float = 30.0  # W4-02: seconds in OPEN before HALF_OPEN
    neo4j_circuit_half_open_max: int = 3  # W4-02: probe calls allowed in HALF_OPEN
    domain_cache_ttl_seconds: int = 30  # W4-03: TTL for async domain pack cache
    domain_cache_maxsize: int = 100  # W4-03: max entries in domain pack cache
    compliance_flush_interval: int = 60  # W4-04: seconds between compliance audit flushes
    compliance_buffer_max: int = 100  # W4-04: max buffered audit entries before forced flush

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Raise if default secrets are used in production environment."""
        if self.l9_env == "prod":
            if self.neo4j_password in _DEFAULT_SECRETS:
                msg = "neo4j_password must be changed from default in production"
                raise ValueError(msg)
            if self.api_secret_key in _DEFAULT_SECRETS:
                msg = "api_secret_key must be changed from default in production"
                raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        return self.l9_env == "prod"

    @property
    def is_development(self) -> bool:
        return self.l9_env == "dev"


# Singleton — import this instance everywhere
settings = Settings()
