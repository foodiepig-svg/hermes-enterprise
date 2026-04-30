# Hermes Enterprise Intelligence Engine

AI-powered detection of revenue leakage, cost anomalies, and lease optimisation opportunities from JD Edwards ERP data.

---

## What It Detects

| Layer | Finding Types |
|---|---|
| **Lease** | Underpriced leases vs. market rate, leases expiring within 6 months |
| **AP / Payments** | Exact duplicate invoices, near-duplicate payments (7-day window, 80%+ match), vendor concentration risk (>30% spend), suspicious early payments, contract-vs-invoice rate drift |
| **AR / Collections** | Overdue invoices: critical >60 days, high >45 days |
| **GL / Ledger** | Round-number anomalies (amounts >$10K with no cents), duplicate GL line items |

---

## Architecture

```
hermes_agent.py          ← Main agent entry point
    ↓
detection/
    detection_engine.py  ← Lease + core AP detection
    ap_ar_gl.py         ← AR collection risk + GL anomalies
    ap_extended.py      ← Vendor risk + payment timing
    ↓
reasoning/
    llm_reasoning.py    ← Groq/Claude/OpenAI enrichment
    ↓
output/findings.json    ← Structured findings (all fields)
    ↓
www/index.html          ← CEO dashboard (dark, browser-based)
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/foodiepig-svg/hermes-enterprise.git
cd hermes-enterprise

# 2. Install dependencies
python3.11 -m pip install --break-system-packages -r requirements.txt

# 3. Set Groq API key
export GROQ_API_KEY=gsk_your_key_here

# 4. Run the agent
python3.11 hermes_agent.py
# Output → output/findings.json

# 5. Open the dashboard
python3.11 -m http.server 8788 --directory www
# → http://localhost:8788
```

---

## Flask API (with CSV Upload)

Start the API server:

```bash
export GROQ_API_KEY=gsk_your_key_here
python3.11 app.py
# → http://localhost:5000
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Upload CSVs + run detection, returns findings + summary |
| `GET` | `/api/summary` | Run detection on sample data, return executive summary |
| `GET` | `/api/findings` | Run detection on sample data, return all findings |
| `GET` | `/api/health` | Health check |

### Upload Format

`POST /api/analyze` accepts:

- **Multipart file upload** — form field names: `leases`, `ap`, `ar`, `gl`, `market_benchmarks`
- **Multipart file upload** — generic `files[]` with filenames `leases.csv`, `ap.csv`, `ar.csv`, `gl.csv`, `market_benchmarks.csv`
- **Raw CSV text** — form fields: `leases`, `ap`, `ar`, `gl`, `market_benchmarks` (raw CSV string)

### Upload Example (curl)

```bash
curl -X POST http://localhost:5000/api/analyze \
  -F "leases=@data/sample_leases.csv" \
  -F "ap=@data/sample_ap.csv" \
  -F "ar=@data/sample_ar.csv" \
  -F "gl=@data/sample_gl.csv"
```

### Response Shape

```json
{
  "findings": [
    {
      "id": "lease_001",
      "type": "lease_underpricing",
      "entity": "Collins St Tower — Suite 100",
      "issue": "Monthly rent $38/psf is 18% below market rate ($46/psf)",
      "financial_impact": "$96,000 / year",
      "confidence": 0.85,
      "evidence": ["Market benchmark for Collins St Class A Office is $46/psf"],
      "explanation": "...",
      "recommendation": "...",
      "urgency": "medium",
      "layer": "lease"
    }
  ],
  "summary": {
    "total_findings": 26,
    "by_urgency": {"critical": 0, "high": 11, "medium": 15, "low": 0},
    "by_type": {"lease_underpricing": 4, "ap_near_duplicate": 3, ...},
    "total_exposure_usd": 419000.00,
    "top_findings": [...]
  },
  "meta": {
    "finding_count": 26,
    "uploaded_files": ["sample_leases.csv", "sample_ap.csv", ...]
  }
}
```

---

## Sample Data

The `data/` directory contains synthetic JDE-style CSV files for demo purposes:

- `sample_leases.csv` — 10 leases (F1501/F1502)
- `sample_ap.csv` — 20 AP invoices (F0411)
- `sample_ar.csv` — 12 AR invoices (F03B11)
- `sample_gl.csv` — 15 GL entries (F0911)
- `market_benchmarks.csv` — market rates by location + asset type

---

## Finding Schema

Every finding includes:

| Field | Description |
|---|---|
| `id` | Unique finding ID |
| `type` | Finding type (e.g. `lease_underpricing`, `ap_duplicate`) |
| `entity` | Affected entity (lease ID, vendor name, invoice number) |
| `issue` | One-line description of the anomaly |
| `financial_impact` | Estimated dollar impact (e.g. `$96,000 / year`) |
| `confidence` | Score 0–1 from detection rules |
| `evidence` | List of supporting data points |
| `explanation` | LLM-generated plain-English explanation |
| `recommendation` | LLM-generated recommended action |
| `urgency` | `critical` / `high` / `medium` / `low` |
| `layer` | Detection layer that produced it |

---

## Configuration

Edit `config.py` to adjust detection thresholds:

```python
LEASE_MARKET_THRESHOLD      = 0.10   # flag if >10% below market
LEASE_EXPIRY_RISK_MONTHS   = 6      # flag if expiring within 6 months
AP_NEAR_DUPLICATE_THRESHOLD= 0.80   # 80% amount match + 7-day window
AP_EARLY_PAYMENT_DAYS      = 15     # flag payments >15 days early
AP_VENDOR_CONCENTRATION    = 0.30   # flag vendor >30% of total spend
AR_HIGH_RISK_DAYS          = 45     # high urgency threshold
AR_CRITICAL_RISK_DAYS      = 60     # critical urgency threshold
GL_ROUND_NUMBER_THRESHOLD  = 10000  # flag round amounts >$10K
```

---

## LLM Providers

Priority order: **Groq** → **Anthropic** → **OpenAI** → **mock**

Set via environment variables:
```bash
export GROQ_API_KEY=gsk_...
export ANTHROPIC_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
```

Mock mode (no API key needed): `python3.11 hermes_agent.py --mock`

---

## Client Package

See `client-package/` for the distributable deliverable — a standalone folder with everything a client needs to run the agent and dashboard. See `client-package/RUNBOOK.md` for instructions.

---

## Deploy to Azure (Production)

```bash
# Using Azure Container Apps
az containerapp up \
  --name hermes-enterprise \
  --image ghcr.io/foodiepig-svg/hermes-enterprise:latest \
  --env GROQ_API_KEY=$GROQ_API_KEY \
  --port 5000 \
  --resource-group hermes-rg
```

Or use the `rcds-azure-deploy` skill for the full RCDS pipeline.

---

*Built on the RCDS framework — Resource Constraint Decision System*
