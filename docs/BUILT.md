# Hermes Enterprise — Build Log

## Session 1 — 27 April 2025

**Context:** Greenfield build. No existing repo, no real data, no deployed infrastructure.

### What was built

- **Repo initialised** at `/Users/WORK/hermes-enterprise/`
- **GitHub repo created** via GitHub API (`foodiepig-svg/hermes-enterprise`)
- **Sample JDE data** created:
  - `data/sample_leases.csv` — 10 synthetic leases (Collins St Tower, Richmond Industrial, etc.)
  - `data/sample_ap.csv` — 20 synthetic AP transactions
  - `data/sample_ar.csv` — 12 synthetic AR transactions with overdue data
  - `data/sample_gl.csv` — 15 synthetic GL entries
  - `data/market_benchmarks.csv` — market rates by location + asset type

### Detection Engine (Layer 1)
- `detection/detection_engine.py` — `detect_lease_opportunities`, `detect_lease_expiry_risk`, `detect_ap_anomalies`
- `detection/ap_ar_gl.py` — `detect_ar_collection_risk`, `detect_ap_double_payments`, `detect_gl_anomalies`
- `detection/ap_extended.py` — `detect_vendor_concentration`, `detect_payment_timing_anomalies`, `detect_payment_term_changes`

### LLM Reasoning
- `reasoning/llm_reasoning.py` — Groq (grok-3) primary, Anthropic → OpenAI → mock fallback
- Individual call per finding (batch LLM pending — see Roadmap)

### CEO Dashboard
- `www/index.html` — dark-themed, KPI strip, sidebar filters, expandable finding cards
- Served via `python3.11 -m http.server 8788 --directory www`
- `www/output/` symlinked to `../output` for findings loading

### First Run Results
- 26 findings across 4 layers
- $419K total simulated exposure
- 11 high-urgency, 15 medium-urgency
- Groq latency: ~14s for 6 findings (individual calls)

### Git
- Initial commit: `09edc2f` — "Initial commit: Hermes Enterprise Intelligence Engine"
- Second commit: `7b45e23` — "Add client package: runbook, config, sample data, cleaned"

---

## Session 2 — 30 April 2025

**Context:** `gh` token missing `read:org` scope. Repo creation via API instead. Client packaging question answered.

### What was built

#### Client Package (`client-package/`)
Self-contained deliverable with:
- `RUNBOOK.md` — step-by-step instructions for non-technical clients
- `hermes_agent.py` — main agent
- `config.py` — adjustable thresholds
- `detection/` + `reasoning/` — all source
- `data/` — sample CSVs (client replaces with real exports)
- `www/` — CEO dashboard
- `requirements.txt` — 3 dependencies
- `output/.gitkeep`

#### GitHub Repo Creation (workaround)
- `gh auth login` failed due to missing `read:org` scope
- Resolved via direct GitHub API: `POST /user/repos` with PAT
- Pushed via `git push -u origin main` with embedded token

#### Flask API (`app.py`)
New file — adds HTTP API capability:
- `POST /api/analyze` — CSV upload + full detection pipeline → JSON findings
- `GET /api/summary` — executive summary from sample data
- `GET /api/findings` — all findings from sample data
- `GET /api/health` — health check
- Serves `www/` as static files
- CORS enabled
- Accepts upload filenames: `leases.csv`, `ap.csv`, `ar.csv`, `gl.csv`, `market_benchmarks.csv`
- Maps client filenames to internal names via `FILE_MAP` (so `leases.csv` → `sample_leases.csv`)
- Cleans up temp upload directory after processing

#### Documentation
- `README.md` — full project docs with API examples, finding schema, config reference
- `docs/SPEC.md` — product specification: detection layers, user flows, financial impact model, urgency mapping, non-goals, roadmap
- `docs/ARCHITECTURE.md` — system architecture with component inventory, data flows, API upload flow, technology choices, deployment options
- `client-package/RUNBOOK.md` — client-facing guide with Option A (API upload) and Option B (standalone)

#### Requirements
- Added: `flask>=3.0.0`, `flask-cors>=6.0.0`
- Updated: `client-package/requirements.txt`

### Git
- Third commit: `732591f` — "Add Flask API with CSV upload, update docs"

---

## Decisions Made

| Decision | Rationale |
|---|---|
| Synthetic data for MVP | No real JDE access yet; demo is convincing with $419K in findings |
| CSV over direct DB | No credentials, no DB integration complexity; JDE exports CSVs natively |
| Groq over OpenAI | Faster, cheaper, good enough reasoning quality |
| Flask over FastAPI | Simpler, well-understood; FastAPI overhead not needed yet |
| Filename mapping on upload | Detection code expects `sample_*` filenames; upload renames transparently |
| No auth on Flask dev server | MVP only; production needs auth before port 5000 is exposed |

---

## Open Items

- [ ] Real JDE data — biggest demo gap; need access to real CSVs
- [ ] Batch LLM calls — single prompt for all findings, ~5s vs ~60s
- [ ] PDF report export — CFO distribution artifact
- [ ] Azure Container Apps deployment — production hosting
- [ ] JDE SmartBar / API direct integration
- [ ] Findings history + status tracking
- [ ] `gh` token with `read:org` scope — for proper `gh repo create` support
