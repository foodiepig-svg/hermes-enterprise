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

## Option A — Run as Flask API (recommended for clients)

The Flask API accepts CSV uploads and returns findings directly. No Python needed on the client side — they just POST files.

### 1. Start the server

```bash
python3.11 -m pip install --break-system-packages -r requirements.txt
export GROQ_API_KEY=gsk_your_key_here
python3.11 app.py
```

Server starts at `http://localhost:5000`.

### 2. Upload CSVs and get findings

```bash
curl -X POST http://localhost:5000/api/analyze \
  -F "leases=@leases.csv" \
  -F "ap=@ap.csv" \
  -F "ar=@ar.csv" \
  -F "gl=@gl.csv"
```

The API accepts:
- Form field names: `leases`, `ap`, `ar`, `gl`, `market_benchmarks`
- Or a generic `files[]` field with any mix of CSV filenames
- Or raw CSV text in form fields named `leases`, `ap`, `ar`, `gl`, `market_benchmarks`

### 3. View the dashboard

```bash
# In a separate terminal:
python3.11 -m http.server 8788 --directory www
```

Open `http://localhost:8788` — findings from the last run are loaded automatically.

### 4. Get just a summary (no dashboard)

```bash
curl http://localhost:5000/api/summary
```

Returns: total findings, breakdown by urgency and type, total exposure in USD, top 5 findings.

---

## Option B — Run standalone (no server)

If you prefer running the agent directly without a server:

### 1. Install dependencies

```bash
python3.11 -m pip install --break-system-packages -r requirements.txt
```

### 2. Place your ERP export files in `data/`

Replace these placeholder files with exports from JD Edwards:

| File | JDE Table | What to Export |
|---|---|---|
| `leases.csv` | F1501 / F1502 | Lease number, location, landlord, monthly rent, expiry date, square footage |
| `ap.csv` | F0411 | Invoice number, vendor, invoice date, due date, amount, payment date |
| `ar.csv` | F03B11 | Invoice number, customer, invoice date, due date, open amount, days overdue |
| `gl.csv` | F0911 | Batch number, account, date, debit amount, credit amount, description |
| `market_benchmarks.csv` | — | (Optional) Location, asset type, market rate psf — default included |

**Rename your files** to match: `sample_leases.csv`, `sample_ap.csv`, `sample_ar.csv`, `sample_gl.csv`.

### 3. Set your Groq API key

```bash
# macOS / Linux
export GROQ_API_KEY=gsk_your_key_here

# Windows (Command Prompt)
set GROQ_API_KEY=gsk_your_key_here
```

### 4. Run the agent

```bash
GROQ_API_KEY=gsk_your_key_here python3.11 hermes_agent.py
```

Typical runtime: **20–40 seconds** on a full dataset.

### 5. View the dashboard

```bash
python3.11 -m http.server 8788 --directory www
# → http://localhost:8788
```

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
  "evidence": ["Market benchmark for Collins St Class A Office is $46/psf"],
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
LEASE_MARKET_THRESHOLD       = 0.10   # flag if >10% below market
LEASE_EXPIRY_RISK_MONTHS    = 6      # flag if expiring within 6 months
AP_NEAR_DUPLICATE_THRESHOLD = 0.80   # 80% amount match + 7-day window
AP_EARLY_PAYMENT_DAYS       = 15     # flag payments >15 days early
AP_VENDOR_CONCENTRATION     = 0.30   # flag vendor >30% of total spend
AR_HIGH_RISK_DAYS           = 45     # high urgency threshold
AR_CRITICAL_RISK_DAYS       = 60     # critical urgency threshold
GL_ROUND_NUMBER_THRESHOLD   = 10000  # flag round amounts >$10K
```

---

## Files Included

```
client-package/
├── RUNBOOK.md                    ← You are here
├── app.py                        ← Flask API server (run with: python3.11 app.py)
├── hermes_agent.py               ← Standalone agent (run with: python3.11 hermes_agent.py)
├── config.py                     ← Detection thresholds
├── requirements.txt              ← Python dependencies
├── detection/
│   ├── detection_engine.py       ← Lease + core AP detection
│   ├── ap_ar_gl.py              ← AR collection + GL anomalies
│   └── ap_extended.py           ← Vendor risk detection
├── reasoning/
│   └── llm_reasoning.py         ← LLM enrichment (Groq / Claude / OpenAI)
├── www/
│   └── index.html               ← CEO dashboard
├── data/
│   ├── sample_leases.csv         ← Sample data (replace with your exports)
│   ├── sample_ap.csv
│   ├── sample_ar.csv
│   ├── sample_gl.csv
│   └── market_benchmarks.csv    ← Default market rates (customise)
└── output/
    └── .gitkeep                  ← Findings written here on standalone run
```

---

## Need Help?

- **No data yet?** The `data/` folder includes sample files — run the agent as-is to see example findings
- **LLM not responding?** Check your `GROQ_API_KEY` is set correctly
- **Upload not working?** The API expects filenames: `leases.csv`, `ap.csv`, `ar.csv`, `gl.csv`, `market_benchmarks.csv`
- **Custom thresholds?** Edit `config.py` before running

---

*Hermes Enterprise Intelligence Engine — built on the RCDS framework*
