# Hermes Enterprise — Intelligence Engine

> *"The decision layer above ERP systems that tells enterprises where they are losing or missing money — and what to do next."*

A reasoning agent that analyses JD Edwards ERP data to detect **revenue leakage**, **cost anomalies**, and **lease optimisation opportunities**, then converts them into explainable, actionable business decisions.

---

## What It Does

```
JDE Extracts (F0911, F0411, F03B11, F1501, F1502)
        │
        ▼
┌─────────────────────────────────────────────┐
│        HERMES INTELLIGENCE ENGINE           │
│                                             │
│  1. Normalise → canonical schema           │
│  2. Detection rules (deterministic)        │
│  3. Benchmark enrichment                   │
│  4. LLM reasoning (explain + recommend)     │
│  5. Structured findings output              │
└─────────────────────────────────────────────┘
        │
        ▼
  JSON Findings + Dashboard
```

## Detection Layers

| Layer | Finds |
|---|---|
| **Lease Optimisation** | Underpriced leases, rent vs market gaps, expiry risk |
| **AP Intelligence** | Duplicate payments, vendor concentration, suspicious timing |
| **AR Intelligence** | Overdue invoices, collection risk, payment pattern anomalies |
| **GL Audit** | Round-number anomalies, duplicate postings, unusual doc types |

## Quick Start

```bash
# Clone
git clone https://github.com/foodiepig-svg/hermes-enterprise.git
cd hermes-enterprise

# Install deps
python3.11 -m pip install groq --break-system-packages

# Run (demo mode — no API key needed)
python3.11 hermes_agent.py

# Run with Grok reasoning
GROQ_API_KEY=your_key python3.11 hermes_agent.py
```

## Dashboard

```bash
# Serve the dashboard (in another terminal)
cd hermes-enterprise/www
python3.11 -m http.server 8788 --directory .
# Open: http://localhost:8788
```

## Configuration

```bash
# Grok (default — fast + cheap)
GROQ_API_KEY=gsk_...

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI GPT
OPENAI_API_KEY=sk-...

# Demo mode (no LLM, deterministic only)
DEMO_MODE=1 python3.11 hermes_agent.py
```

## Project Structure

```
hermes-enterprise/
├── data/                       ← JDE sample data (CSV)
│   ├── sample_leases.csv        ← F1501 / F1502 format
│   ├── sample_ap.csv            ← F0411 format
│   ├── sample_ar.csv            ← F03B11 format
│   ├── sample_gl.csv            ← F0911 format
│   └── market_benchmarks.csv    ← Market rate reference
├── detection/                   ← Deterministic rule engine
│   ├── detection_engine.py      ← Core: lease + AP detection
│   ├── ap_ar_gl.py              ← AR + GL detection
│   └── ap_extended.py           ← Extended AP analysis
├── reasoning/
│   └── llm_reasoning.py         ← LLM reasoning layer
├── hermes_agent.py              ← Main agent loop
├── www/                         ← Dashboard
│   └── index.html
└── output/
    └── findings.json             ← Structured output
```

## Output Format

Each finding follows this structure:

```json
{
  "type": "Lease Underpricing",
  "entity": "Collins St Tower - Unit 12B",
  "entity_id": "L-1501-B",
  "issue": "Rent 15.8% below market benchmark",
  "financial_impact": "$18K annual upside at risk",
  "confidence": "88%",
  "evidence": [
    "F1501 lease rate = $80.00/sqm",
    "Market benchmark = $95.00/sqm"
  ],
  "explanation": "Plain-English reasoning from LLM...",
  "recommendation": "Renegotiate at next renewal...",
  "expected_outcome": "Align to market rate...",
  "urgency": "High",
  "owner": "Asset Manager",
  "jde_sources": ["F1501 (Lease Master)", "F1502 (Lease Terms)"]
}
```

## Design Principles

1. **Deterministic first, AI second** — calculations are reproducible; LLM only for reasoning + narrative
2. **Explainability is mandatory** — every output includes source tables and calculation logic
3. **Actionability > insight** — every finding has a recommended action and financial implication
4. **Human-in-the-loop ready** — findings are structured for approval/rejection workflows
