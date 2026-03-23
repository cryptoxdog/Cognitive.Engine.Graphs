# GMP-100: README Generation Project Tracker

**GMP ID:** GMP-100
**Project:** README Gold Standard Generation
**Status:** STRATEGY/PLAN MODE (not locked)
**Created:** 2026-01-18
**Primary Pack:** `codegen/README-CodeGen/`

---

## 🎯 Project Goal

Generate gold-standard READMEs for all L9 modules using:
1. **Automated fact extraction** (`scripts/generate_readme_superprompt.py`)
2. **Perplexity deep research** for rich content
3. **Validation against extracted facts** (anti-drift)

---

## 📊 Module Categories & Status

### CATEGORY 1: Core Agents
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Agent Executor | `core/agents/` | ⏳ TODO | | | |
| Cursor Agent | `agents/cursor/` | ⏳ TODO | | | |
| Research Agent | `agents/research_agent/` | ⏳ TODO | | | |
| L CTO Agent | `agents/l_cto.py` | ⏳ TODO | | | |
| Mac Agent | `mac_agent/` | ⏳ TODO | | | |
| Email Agent | `email_agent/` | ⏳ TODO | | | |
| CodeGen Agent | `agents/codegenagent/` | ⏳ TODO | | | |

### CATEGORY 2: Memory Stack
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Memory Substrate | `memory/` | ⏳ TODO | | | |
| MCP Memory Server | `mcp_memory/` | ⏳ TODO | | | |
| Predictive Warming | `memory/warming_*` | ⏳ TODO | | | |
| Belief Revision | `memory/` (Stage 4) | ⏳ TODO | | | |

### CATEGORY 3: Orchestration
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Research Swarm | `orchestrators/research_swarm/` | ⏳ TODO | | | |
| Task Router | `orchestration/` | ⏳ TODO | | | |
| Plan Executor | `orchestration/plan_executor.py` | ⏳ TODO | | | |
| Unified Controller | `orchestration/` | ⏳ TODO | | | |

### CATEGORY 4: Tool Infrastructure
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Tool Graph | `core/tools/` | ⏳ TODO | | | |
| Tool Registry | `core/tools/registry_adapter.py` | ⏳ TODO | | | |
| Research Tools | `core/tools/research_tools.py` | ⏳ TODO | | | |

### CATEGORY 5: API Layer
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Main API Server | `api/` | ⏳ TODO | | | |
| Research Routes | `api/routes/research*.py` | ⏳ TODO | | | |
| Agent Routes | `api/agent_routes.py` | ⏳ TODO | | | |

### CATEGORY 6: Research Services
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Research Graph | `services/research/` | ⏳ TODO | | | |
| Perplexity Client | `services/research/tools/perplexity_client.py` | ⏳ TODO | | | |
| Insight Extractor | `services/research/insight_extractor.py` | ⏳ TODO | | | |
| Planner Agent | `services/research/agents/planner_agent.py` | ⏳ TODO | | | |
| Critic Agent | `services/research/agents/critic_agent.py` | ⏳ TODO | | | |

### CATEGORY 7: Runtime Infrastructure
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Task Queue | `runtime/` | ⏳ TODO | | | |
| Redis Client | `runtime/redis_client.py` | ⏳ TODO | | | |
| Rate Limiter | `runtime/rate_limiter.py` | ⏳ TODO | | | |
| WebSocket Orchestrator | `runtime/websocket_orchestrator.py` | ⏳ TODO | | | |

### CATEGORY 8: Kernels & Governance
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| Kernel Loader | `core/kernels/` | ⏳ TODO | | | |
| GMP Protocol | `agents/cursor/gmp_protocol/` | ⏳ TODO | | | |

### CATEGORY 9: World Model
| Module | Path | Status | Superprompt | P Output | Validated |
|--------|------|--------|-------------|----------|-----------|
| World Model Service | `world_model/` | ⏳ TODO | | | |
| IR Engine | `ir_engine/` | ⏳ TODO | | | |
| Simulation Engine | `simulation/` | ⏳ TODO | | | |

---

## 📈 Progress Summary

| Category | Total | Done | % |
|----------|-------|------|---|
| Core Agents | 7 | 0 | 0% |
| Memory Stack | 4 | 0 | 0% |
| Orchestration | 4 | 0 | 0% |
| Tool Infrastructure | 3 | 0 | 0% |
| API Layer | 3 | 0 | 0% |
| Research Services | 5 | 0 | 0% |
| Runtime Infrastructure | 4 | 0 | 0% |
| Kernels & Governance | 2 | 0 | 0% |
| World Model | 3 | 0 | 0% |
| **TOTAL** | **35** | **0** | **0%** |

---

## 🔧 Workflow

### Per-Module Process

```
1. EXTRACT FACTS
   python scripts/generate_readme_superprompt.py --path <module_path> -v \
     --output agents/cursor/perplexity_research_results/01-18-2026\ -\ readme-generation-gmp100/superprompts/<module>.md

2. PASTE TO PERPLEXITY
   - Copy superprompt to Perplexity
   - Wait for response

3. SAVE P OUTPUT
   - Save to: .../01-18-2026 - readme-generation-gmp100/p-outputs/README-<module>.md

4. VALIDATE
   - Cross-check every class/method against extracted facts
   - Flag any hallucinations

5. DEPLOY
   - Copy validated README to <module_path>/README.md
   - Update tracker status
```

### Batch Strategy

**Batch by category** for efficiency:
- Process all Memory modules together (similar context)
- Process all Orchestration modules together
- etc.

---

## 📁 Folder Structure

```
agents/cursor/perplexity_research_results/
└── 01-18-2026 - readme-generation-gmp100/
    ├── GMP-100-README-GENERATION-TRACKER.md  ← This file
    ├── superprompts/
    │   ├── core-agents.md
    │   ├── memory.md
    │   └── ...
    └── p-outputs/
        ├── README-core-agents.md
        ├── README-memory.md
        └── ...
```

---

## 🛠️ Tools

| Tool | Purpose | Location |
|------|---------|----------|
| `generate_readme_superprompt.py` | Extract facts → generate superprompt | `scripts/` |
| README-CodeGen Pack | Templates + super prompt | `codegen/README-CodeGen/` |
| `labs-research-super-prompt.md` | Research prompt template | `codegen/README-CodeGen/` |

---

## ⚠️ Notes

1. **C Superprompt Pack** (`codegen/Perplexity-Search-Pack/perplexity-c-superprompt-pack/`) is for C developers using libcurl — **NOT applicable** to our Python/README workflow.

2. **Primary Pack** is `codegen/README-CodeGen/` which has:
   - `README.gold-standard.md` — Template
   - `labs-research-super-prompt.md` — System prompt for P
   - `subsystem-readmes-complete.md` — Examples

3. **Anti-Drift Protocol:**
   - Always provide extracted facts in superprompt
   - Never ask P to "analyze" or "discover" — give it facts
   - Validate output against facts before deploy

---

*Last Updated: 2026-01-18*
