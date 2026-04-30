# Hermes Enterprise Intelligence Engine — Client Package

## What This Does

Hermes analyses your JD Edwards ERP data and surfaces three types of findings:

| Finding Type | What It Means | Financial Impact |
|---|---|---|
| **Lease Optimisation** | You're paying above-market rent, or have expiring leases without a renewal strategy | Reduce lease costs by 10–25% |
| **AP / Payment Anomalies** | Duplicate payments, suspicious early payments, or vendor rate drift | Recover 1–5% of annual AP spend |
| **AR Collection Risk** | Overdue invoices not being followed up | Unlock 30–90 days of locked cash flow |

---

## Prerequisites

- **Python 3.11+** — download from https://www.python.org/downloads/
- **Groq API key** — get free at https://console.groq.com/keys (free tier: 30 requests/min)

---

## Setup (5 minutes)

### 1. Place your ERP export files in `data/`

Replace these placeholder files with exports from JD Edwards:

| File | JDE Table | What to Export |
|---|---|---|
| `leases.csv` | F1501 / F1502 | Lease number, location, landlord, monthly rent, expiry date, square footage |
| `ap.csv` | F0411 | Invoice number, vendor, invoice date, due date, amount, payment date |
| `ar.csv` | F03B11 | Invoice number, customer, invoice date, due date, open amount, days overdue |
| `gl.csv` | F0911 | Batch number, account, date, debit amount, credit amount, description |
| `market_benchmarks.csv` | — | (Optional) Location, asset type, market rate psf — included as default |

**Export format:** CSV with headers. Column names are flexible — the engine matches common JDE column names automatically.

### 2. Set your Groq API key

```bash
# macOS / Linux
export GROQ_API_KEY=gsk_your_key_here

# Windows (Command Prompt)
set GROQ_API_KEY=gsk_your_key_here
```

### 3. Install dependencies

```bash
python3.11 -m pip install --break-system-packages beautifulsoup4 groq lxml
```

---

## Run the Agent

```bash
GROQ_API_KEY=gsk_your_key_here python3.11 hermes_agent.py
```

The agent will:
1. Load and validate your data files
2. Run all detection layers (lease, AP, AR, GL)
3. Enrich findings with LLM-generated explanations
4. Write results to `output/findings.json`

Typical runtime: **20–40 seconds** on a sample dataset.

---

## View the Dashboard

```bash
python3.11 -m http.server 8788 --directory www
```

Then open in your browser:

```
http://localhost:8788
```

The dashboard shows:
- Total findings count and urgency breakdown
- Total estimated financial exposure
- Filterable cards for each finding with full explanation

---

## Understanding the Output

Each finding in `output/findings.json` follows this structure:

```json
{
  "id": "lease_001",
  "type": "lease_underpricing",
  "entity": "Collins St Tower — Suite 100",
  "issue": "Monthly rent $38/psf is 18% below market rate ($46/psf)",
  "financial_impact": "$96,000 / year",
  "confidence": 0.85,
  "evidence": "Market benchmark for Collins St Class A Office is $46/psf",
  "explanation": "This lease appears significantly underpriced relative to current market conditions...",
  "recommendation": "Approach the tenant 90 days before lease expiry to negotiate a market-rate renewal...",
  "urgency": "medium",
  "layer": "lease"
}
```

**Urgency levels:**
- `critical` — act within 7 days (e.g., duplicate payment detected)
- `high` — act within 30 days (e.g., lease expiring in <90 days)
- `medium` — plan within 60 days (e.g., AR 45–60 days overdue)
- `low` — review quarterly (e.g., market-rate underpricing)

---

## Configuration

Edit `config.py` to adjust detection thresholds:

```python
# Lease: minimum deviation from market rate to flag (default 10%)
LEASE_MARKET_THRESHOLD = 0.10

# AP: minimum amount match % for near-duplicate detection (default 80%)
AP_NEAR_DUPLICATE_THRESHOLD = 0.80

# AP: days early to flag suspicious early payments (default 15)
AP_EARLY_PAYMENT_DAYS = 15

# AR: days overdue to flag as high/critical risk (default 45/60)
AR_HIGH_RISK_DAYS = 45
AR_CRITICAL_RISK_DAYS = 60
```

---

## Files Included

```
client-package/
├── RUNBOOK.md                    ← You are here
├── hermes_agent.py               ← Main agent
├── config.py                     ← Detection thresholds
├── requirements.txt              ← Python dependencies
├── detection/
│   ├── detection_engine.py       ← Core lease + AP detection
│   ├── ap_ar_gl.py               ← AR + GL detection
│   └── ap_extended.py            ← Vendor risk detection
├── reasoning/
│   └── llm_reasoning.py          ← LLM enrichment
├── www/
│   └── index.html                ← CEO dashboard
├── data/
│   ├── leases.csv                ← PLACEHOLDER — replace with your data
│   ├── ap.csv                    ← PLACEHOLDER
│   ├── ar.csv                    ← PLACEHOLDER
│   ├── gl.csv                    ← PLACEHOLDER
│   └── market_benchmarks.csv     ← Default market rates (customise)
└── output/
    └── .gitkeep                  ← Findings written here on run
```

---

## Need Help?

- **No data yet?** The `data/` folder includes sample files — run the agent as-is to see example findings
- **LLM not responding?** Check your `GROQ_API_KEY` is set correctly
- **Custom thresholds?** Edit `config.py` before running

---

*Hermes Enterprise Intelligence Engine — built on the RCDS framework*
