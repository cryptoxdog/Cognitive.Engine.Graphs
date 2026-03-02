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

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = ["*"]

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
    kge_embedding_dim: int = 300
    kge_confidence_threshold: float = 0.3

    @property
    def is_production(self) -> bool:
        return self.l9_env == "prod"

    @property
    def is_development(self) -> bool:
        return self.l9_env == "dev"


# Singleton — import this instance everywhere
settings = Settings()
