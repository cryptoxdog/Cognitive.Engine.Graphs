# Perplexity Research Results — SOP

**Location:** `agents/cursor/perplexity_research_results/`
**Status:** GITIGNORED (ephemeral storage)
**Review Cycle:** Weekly archive/delete

---

## 🔒 SOP (LOCKED)

### Folder Purpose

This folder stores **Perplexity research outputs** — deep research results, generated READMEs, implementation specs, and TODO plans that come from AI research sessions.

### Folder Naming Convention

```
MM-DD-YYYY - <description>/
```

**Examples:**
- `01-15-2026 - memory-substrate-belief-revision/`
- `01-18-2026 - readme-gold-standard/`
- `01-20-2026 - predictive-memory-warming/`

### File Naming

Within each project folder, name files by their purpose:
- `PHASE-0-TODO-*.md` — Locked TODO plans ready for GMP execution
- `stage*_*.md` — Perplexity research outputs (raw)
- `README-*.md` — Generated README files
- `superprompt-*.md` — Superprompts used for generation
- `validation-*.md` — Validation results

### Lifecycle

```
1. CREATE project subfolder (MM-DD-YYYY - description)
2. SAVE Perplexity outputs to subfolder
3. REVIEW weekly (Sunday)
4. ARCHIVE useful content → appropriate repo location
5. DELETE reviewed content
```

### Why Gitignored

- **Reduces AI drift** — Prevents Claude/Cursor from ingesting raw research
- **Ephemeral nature** — Research outputs are intermediate, not canonical
- **Weekly cleanup** — Forces review and curation

---

## 📁 Current Structure

```
perplexity_research_results/
├── README-SOP.md                    ← This file (SOP documentation)
├── 01-15-2026 - memory-substrate-stages/
│   ├── PHASE-0-TODO-STAGE-4-BELIEF-REVISION.md
│   ├── stage4_belief_revision_system.md
│   └── stage6_multi_agent_consensus.md
└── [new project folders as created]
```

---

## 🔧 Generating README Superprompts

Use the enhanced script to extract facts and generate superprompts:

```bash
# Generate superprompt for any path
python scripts/generate_readme_superprompt.py --path agents/cursor -v

# Output to file
python scripts/generate_readme_superprompt.py \
  --path agents/codegenagent \
  --output agents/cursor/perplexity_research_results/01-18-2026\ -\ readme-project/superprompt-codegenagent.md
```

### Workflow

1. **Extract facts** with script
2. **Copy superprompt** to Perplexity
3. **Paste Perplexity output** to project subfolder
4. **Validate** against extracted facts
5. **Deploy** validated README to target location

---

## ✅ Status of Existing Files

| File | Status | Next Action |
|------|--------|-------------|
| `PHASE-0-TODO-STAGE-4-BELIEF-REVISION.md` | ✅ TODO LOCKED | Execute GMP |
| `stage4_belief_revision_system.md` | ✅ Research complete | Reference for GMP |
| `stage6_multi_agent_consensus.md` | ⏳ Future stage | Hold for Stage 6 |

---

*Last updated: 2026-01-18*
