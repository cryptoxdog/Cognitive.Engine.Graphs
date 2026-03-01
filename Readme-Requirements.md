<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Reset, Re-align \& Lock In- No Drifting!

Stay procured we’re almost finished building the graph project. Finish line in sight

Please make these to complete
•	3 real files (`requirements.txt`, `settings.py`, `dependencies.py`

**4 files, 226 lines — P0 blockers cleared.**

***

## File Mapping

| Generated File | Target Path | Purpose |
| :-- | :-- | :-- |
| `requirements.txt` | `requirements.txt` | Pinned production deps from pyproject.toml |
| `requirements-dev.txt` | `requirements-dev.txt` | Test/lint deps, includes `-r requirements.txt` |
| `engine-config-settings.py` | `engine/config/settings.py` | pydantic-settings `Settings` class |
| `engine-api-dependencies.py` | `engine/api/dependencies.py` | FastAPI `Depends()` injection |


***

## How They Wire In

**`settings.py`** reads every env var from `.env.example` — same names, same defaults . Exports a singleton `settings` instance that the rest of the engine imports:

- `neo4j_uri`, `neo4j_username`, `neo4j_password` → consumed by `dependencies.py` to init `GraphDriver`[^1]
- `domains_root` → consumed by `dependencies.py` to init `DomainPackLoader`[^2]
- `redis_url` → lazy-init Redis client
- Scoring weights (`w_structural`, `w_geo`, etc.) → match the spec's config reference[^3]
- Decay half-lives → match the temporal decay system in `engine-core-modules.py`[^1]

**`dependencies.py`** provides the `Depends()` functions that `match.py`, `sync.py`, and `health.py` already import:[^4]

- `get_graph_driver()` → returns the shared async Neo4j driver
- `get_domain_loader()` → returns the cached domain pack loader
- `get_redis()` → lazy Redis with graceful degradation
- `startup()` / `shutdown()` → called from `create_app()` lifespan

**`requirements.txt`** pins every dep from `pyproject.toml` with `>=X,<Y` bounds — works for Docker builds and non-Poetry envs .
<span style="display:none">[^5]</span>

<div align="center">⁂</div>

[^1]: engine-core-modules.py

[^2]: engine-config-loader.py

[^3]: SPEC_v1.1_COGNITIVE_ENGINE.md

[^4]: engine-final-components.py

[^5]: engine-config-pkg-init.py

