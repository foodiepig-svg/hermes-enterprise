# Hermes Enterprise — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                            │
│                                                             │
│   hermes_agent.py (CLI)          app.py (Flask API)         │
│   python3.11 hermes_agent.py     python3.11 app.py          │
│                                 POST /api/analyze            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                               │
│                                                             │
│   data/                                                    │
│   ├── sample_leases.csv   (F1501/F1502 synthetic)         │
│   ├── sample_ap.csv       (F0411 synthetic)                │
│   ├── sample_ar.csv       (F03B11 synthetic)               │
│   ├── sample_gl.csv       (F0911 synthetic)                 │
│   └── market_benchmarks.csv                                 │
│                                                             │
│   upload/ (temp, API mode only)                            │
│   └── [renamed to match expected filenames]                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 DETECTION LAYER                             │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ detection_   │  │  ap_ar_gl.py  │  │ ap_extended.py │  │
│  │ engine.py     │  │              │  │                │  │
│  │              │  │  AR risk      │  │ Vendor conc.   │  │
│  │ Lease        │  │  GL anomaly   │  │ Early payment  │  │
│  │ underpricing │  │  AP double    │  │ Rate drift     │  │
│  │ Lease expiry │  │  payments     │  │                │  │
│  │ AP duplicate │  │              │  │                │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                  │                   │            │
│         └──────────────────┴───────────────────┘            │
│                          │                                  │
│                    RawFinding[]                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                LLM REASONING LAYER                          │
│                                                             │
│  reasoning/llm_reasoning.py                                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ enrich_findings(findings: list[RawFinding])          │  │
│  │                                                      │  │
│  │  Provider priority:                                 │  │
│  │  1. Groq (grok-3) — fastest, free tier available    │  │
│  │  2. Anthropic (claude-sonnet-4)                    │  │
│  │  3. OpenAI (gpt-4o-mini)                           │  │
│  │  4. Mock fallback — returns static text             │  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                  │
│              EnrichedFinding[] (dict)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                              ▼
┌───────────────────────┐    ┌───────────────────────────────┐
│   OUTPUT LAYER        │    │   PRESENTATION LAYER          │
│                       │    │                               │
│ output/findings.json  │    │ www/index.html               │
│                       │    │                               │
│ All enriched findings │    │ Dark-themed CEO dashboard    │
│ Written by agent      │    │ Served by Flask static        │
│ Read by dashboard     │    │ or http.server                │
│                       │    │                               │
│                       │    │ KPI strip (findings/exposure) │
│                       │    │ Sidebar filters               │
│                       │    │ Finding cards                 │
└───────────────────────┘    └───────────────────────────────┘
```

---

## Component Inventory

### `hermes_agent.py` — CLI Entry Point
- Loads data paths from `data/` directory
- Calls all detection modules sequentially
- Calls LLM enrichment
- Writes results to `output/findings.json`
- Returns exit code 0 on success

### `app.py` — Flask API Server
- Serves on port 5000 (configurable via `PORT` env var)
- `POST /api/analyze` — accepts CSV uploads, runs full pipeline, returns JSON
- `GET /api/summary` — executive summary only
- `GET /api/findings` — all findings only
- `GET /api/health` — health check
- Static file serving for `www/`
- CORS enabled for all routes

### `detection/detection_engine.py`
- Functions: `load_leases`, `load_ap_transactions`, `load_market_rates`
- Detection: `detect_lease_opportunities`, `detect_lease_expiry_risk`, `detect_ap_anomalies`
- Returns: list of `RawFinding` dataclass instances

### `detection/ap_ar_gl.py`
- Functions: `load_ar_transactions`, `load_gl_entries`
- Detection: `detect_ar_collection_risk`, `detect_ap_double_payments`, `detect_gl_anomalies`
- Returns: list of `RawFinding` dataclass instances

### `detection/ap_extended.py`
- Function: `run_ap_extended`
- Detection: `detect_vendor_concentration`, `detect_payment_timing_anomalies`, `detect_payment_term_changes`
- Returns: list of `RawFinding` dataclass instances

### `reasoning/llm_reasoning.py`
- Function: `enrich_findings(findings)` — takes raw findings, returns enriched
- **Batch processing:** all findings passed in ONE LLM call (single prompt, single response)
- Provider fallback: Groq → Anthropic → OpenAI → mock
- Mock fallback if no API key or batch parse fails
- Timeout: 30s per call
- System prompt: senior financial analyst persona, JSON-only output

### `www/index.html` — CEO Dashboard
- Single-page HTML/JS application
- Loads `output/findings.json` via fetch on load
- No build step, no framework — vanilla JS
- Auto-populates: KPI strip, sidebar type filters, finding cards
- Filter state managed in JS memory (no URL params)

### `output/report_generator.py`
- Function: `generate_pdf_report(findings, summary, output_path)` → PDF file path
- Uses ReportLab PLATYPUS for professional layout
- Dark-themed content matching the dashboard aesthetic
- Sections: header with title + date, KPI strip, findings detail table
- Urgency colour coding: critical=red, high=red, medium=amber, low=green
- Truncates long text fields for table layout

### `config.py` — Detection Thresholds
- All numeric thresholds centralised here
- No hardcoded magic numbers in detection code
- Clients can adjust without reading detection source

---

## Data Flow (Full Run)

```
1. hermes_agent.py starts
       ↓
2. Load: leases, AP, AR, GL, market benchmarks
       ↓
3. Layer 1: detect_lease_opportunities()
             detect_lease_expiry_risk()
             detect_ap_anomalies()
       ↓
4. Layer 2: detect_ar_collection_risk()
             detect_ap_double_payments()
             detect_gl_anomalies()
       ↓
5. Layer 3: run_ap_extended()
             detect_vendor_concentration()
             detect_payment_timing_anomalies()
             detect_payment_term_changes()
       ↓
6. Concatenate all findings → findings[]
       ↓
7. enrich_findings(findings)
       For each finding:
         → call LLM provider
         → extract explanation + recommendation
         → attach to finding dict
       ↓
8. Write output/findings.json
       ↓
9. Dashboard loads findings.json via fetch
       ↓
10. CEO reads findings
```

---

## API Upload Flow

```
Client
  │
  │ POST /api/analyze
  │ Content-Type: multipart/form-data
  │ Fields: leases, ap, ar, gl, market_benchmarks
  ▼
app.py
  │
  ├─→ tempfile.mkdtemp() → /tmp/hermes_upload_XXXXX/
  │
  ├─→ FILE_MAP = {
  │     'leases.csv'         → 'sample_leases.csv',
  │     'ap.csv'             → 'sample_ap.csv',
  │     'ar.csv'             → 'sample_ar.csv',
  │     'gl.csv'             → 'sample_gl.csv',
  │     'market_benchmarks.csv' → 'market_benchmarks.csv'
  │   }
  │
  ├─→ f.save(os.path.join(upload_dir, mapped_name))
  │
  ├─→ run_detection(upload_dir)
  │     (same detection + LLM pipeline)
  │
  ├─→ make_summary(findings)
  │
  ├─→ shutil.rmtree(upload_dir)  # cleanup
  │
  ▼
Response JSON:
  { findings: [...], summary: {...}, meta: {...} }
```

---

## Technology Choices

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11 | Type hints, dict union operators, required by detection modules |
| HTTP Server | Flask + flask-cors | Lightweight, known pattern, easy client integration |
| LLM | Groq (grok-3) | Fastest (~2s/call), free tier, good reasoning quality |
| LLM fallback | Anthropic → OpenAI | Graceful degradation if Groq is unavailable |
| Dashboard | Vanilla HTML/JS | No build step, zero dependencies, runs in any browser |
| Data format | CSV | Native JDE export format, no DB credentials needed |
| Findings output | JSON | Structured, parseable, dashboard-consumable |

---

## Security Notes

- **API key handling:** `GROQ_API_KEY` read from environment at runtime — never stored in code or committed to git
- **File upload:** CSVs saved to a unique temp directory per request, deleted immediately after processing
- **Git history:** API keys must not be committed — checked by `.gitignore`
- **CORS:** Enabled for all origins in dev mode; restrict to known origins before production deployment
- **No authentication on Flask dev server** — do not expose port 5000 publicly without adding auth (see Azure deploy option)

---

## Deployment Options

### Local development
```bash
python3.11 app.py  # port 5000
python3.11 -m http.server 8788 --directory www  # port 8788
```

### Azure Container Apps
```bash
az containerapp up \
  --name hermes-enterprise \
  --image ghcr.io/foodiepig-svg/hermes-enterprise:latest \
  --env GROQ_API_KEY=$GROQ_API_KEY \
  --port 5000
```

### Docker
```bash
docker build -t hermes-enterprise .
docker run -e GROQ_API_KEY=$GROQ_API_KEY -p 5000:5000 hermes-enterprise
```
