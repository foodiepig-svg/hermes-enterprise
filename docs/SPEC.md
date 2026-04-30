# Hermes Enterprise — Product Specification

## Overview

**What it is:** An AI-powered ERP intelligence agent that connects to JD Edwards data and surfaces actionable financial findings — revenue leakage, cost anomalies, and lease optimisation opportunities.

**Who it's for:** Finance leaders, CFOs, and operations teams at companies running JD Edwards who want to find money they're leaving on the table.

**Core loop:**
1. Load JDE CSV exports (leases, AP, AR, GL)
2. Run deterministic detection rules across 4 layers
3. Enrich each finding with LLM-generated explanation and recommendation
4. Output structured JSON + interactive CEO dashboard

---

## Detection Layers

### Layer 1 — Lease Opportunities
- **Underpriced lease detection** — flags leases where rent/psf is more than 10% below market rate for comparable location + asset type
- **Expiry risk** — flags leases expiring within 6 months without a renewal date set

**JDE tables:** F1501 (Lease Header), F1502 (Lease Detail)

### Layer 2 — Accounts Payable
- **Exact duplicate invoices** — same vendor + amount + date (different invoice number)
- **Near-duplicate payments** — same vendor + ≥80% amount + within 7-day window
- **Vendor concentration** — any vendor representing >30% of total AP spend
- **Early payment anomaly** — payments made >15 days before due date
- **Contract rate drift** — invoice rate differs from contract rate by >20%

**JDE table:** F0411 (AP Invoice)

### Layer 3 — Accounts Receivable
- **Collection risk** — overdue invoices categorised as high (>45 days) or critical (>60 days)

**JDE table:** F03B11 (AR Open)

### Layer 4 — General Ledger
- **Round-number anomaly** — amounts >$10,000 with zero cents (potential inflated entries)
- **Duplicate GL lines** — same account + amount + date (different batch number)

**JDE table:** F0911 (GL Transactions)

---

## User Flows

### Flow 1 — Demo (no real data)
User clones repo, sets `GROQ_API_KEY`, runs `hermes_agent.py`. Agent runs on synthetic sample data. Dashboard shows 26 findings totalling ~$419K in simulated exposure.

### Flow 2 — CSV Upload via API
Client exports CSVs from JDE → uploads via `POST /api/analyze` → receives findings + executive summary. No Python or agent setup required on client side.

### Flow 3 — Standalone with Real Data
Client replaces sample CSVs in `data/` with their real JDE exports, runs `hermes_agent.py` locally, opens dashboard at `localhost:8788`.

---

## LLM Enrichment

Every raw finding is enriched with:
- **explanation** — plain-English description of why this was flagged and what it means financially
- **recommendation** — specific next step (who to talk to, what to check, when to act)

**Provider priority:** Groq → Anthropic Claude → OpenAI GPT → mock fallback
**Batch vs. individual:** Currently individual calls per finding (~14s for 6 findings). Batching all findings into a single call reduces latency ~70%.

---

## Output

### Structured JSON (`output/findings.json`)
Every finding has: `id`, `type`, `entity`, `issue`, `financial_impact`, `confidence`, `evidence`, `explanation`, `recommendation`, `urgency`, `layer`.

### Executive Dashboard (`www/index.html`)
Dark-themed browser UI with:
- KPI strip: total findings, high/medium/low counts, total exposure
- Sidebar: urgency filters + type filters (auto-populated from findings)
- Finding cards: entity, issue, financial impact, confidence, expandable explanation + recommendation

### Summary (`/api/summary`)
HTTP endpoint returning: total count, urgency breakdown, type breakdown, total exposure USD, top 5 findings.

---

## Financial Impact Model

Each finding includes a `financial_impact` string (e.g., `"$96,000 / year"` or `"$12,500 recovered"`). Impact is computed at detection time:

| Finding Type | Impact Calculation |
|---|---|
| Lease underpricing | `(market_rate - actual_rate) × sq_ft × 12` |
| Duplicate payment | Full invoice amount recovered |
| Near-duplicate payment | Full invoice amount (suspected duplicate) |
| Vendor concentration | Not a direct recovery — flags risk |
| Early payment | Discount lost = `amount × discount_rate × days_early / 365` |
| Contract rate drift | `contract_rate - invoice_rate × quantity` |
| AR collection risk | Outstanding invoice amount |
| Round-number anomaly | Flag only — requires investigation |
| GL duplicate | Flag only — requires investigation |

---

## Urgency Mapping

| Urgency | Trigger | SLA |
|---|---|---|
| `critical` | Duplicate payment confirmed, AR >60 days overdue | Act within 7 days |
| `high` | Lease expiring <90 days, AR 45–60 days, vendor >50% concentration | Act within 30 days |
| `medium` | Lease underpriced >15%, AR 30–45 days, early payment anomaly | Plan within 60 days |
| `low` | Market-rate underpricing, GL round-number flag | Review quarterly |

---

## Non-Goals (Out of Scope)

- Direct JDE ERP connection (no DB credentials, no API integration)
- Real-time data monitoring / alerting
- PDF report generation (planned)
- Multi-tenant / user auth
- Data persistence (findings are ephemeral — written to `output/findings.json`)

---

## Future Roadmap

1. **PDF export** — one-click findings → formatted PDF report for CFO distribution
2. **Batch LLM calls** — single prompt with all findings → ~5s total vs ~60s sequential
3. **Azure Container Apps deployment** — containerised API with HTTPS + auth
4. **JDE SmartBar integration** — direct F1501/F0411/F03B11/F0911 reads via JDE API
5. **Findings history** — track finding status (open/investigating/resolved) over time
6. **Anomaly baseline** — ML-based anomaly detection on top of rule-based detection
