# Cursor-Native GMP Action Files

These files are designed for use with Cursor's `/gmp` command to integrate the GMP v2.0 learning system.

## Usage

```bash
/gmp @codegen/prompts/gmp-v2/cursor-actions/GMP-Action-Wire-Learning-Engine.md
```

## Available Actions

| File                                    | GMP ID | Description                  | Depends On     |
| --------------------------------------- | ------ | ---------------------------- | -------------- |
| `GMP-Action-Wire-Learning-Engine.md`    | GMP-92 | Wire engine to api/server.py | Migration 0021 |
| `GMP-Action-Add-Learning-API-Routes.md` | GMP-93 | Create API endpoints         | GMP-92         |
| `GMP-Action-Create-Learning-Tests.md`   | GMP-94 | Create unit tests            | None           |

## Execution Order

```
1. Run migration: psql -f migrations/0021_gmp_learning.sql
2. /gmp @GMP-Action-Wire-Learning-Engine.md
3. /gmp @GMP-Action-Add-Learning-API-Routes.md
4. /gmp @GMP-Action-Create-Learning-Tests.md
```

## What's Already Complete

| Component     | Status  | Location                           |
| ------------- | ------- | ---------------------------------- |
| Python Module | ✅ 100% | `core/gmp/meta_learning_engine.py` |
| SQL Migration | ✅ 100% | `migrations/0021_gmp_learning.sql` |
| Module Init   | ✅ 100% | `core/gmp/__init__.py`             |

## What These Actions Create

| Component     | Status    | Location                          |
| ------------- | --------- | --------------------------------- |
| Server Wiring | ⏳ GMP-92 | `api/server.py`                   |
| API Routes    | ⏳ GMP-93 | `api/routes/gmp_learning.py`      |
| Unit Tests    | ⏳ GMP-94 | `tests/gmp/test_meta_learning.py` |

## API Endpoints (After GMP-93)

| Method | Path                           | Description                  |
| ------ | ------------------------------ | ---------------------------- |
| GET    | `/api/gmp/autonomy-level`      | Current level (L2/L3/L4/L5)  |
| GET    | `/api/gmp/graduation-status`   | Can graduate to next level?  |
| POST   | `/api/gmp/graduate`            | Attempt graduation           |
| GET    | `/api/gmp/heuristics`          | Active learned heuristics    |
| GET    | `/api/gmp/analytics`           | 30-day execution analytics   |
| POST   | `/api/gmp/log-execution`       | Log GMP result               |
| POST   | `/api/gmp/generate-heuristics` | Trigger heuristic generation |
