"""Hermes Enterprise Intelligence Layer — Main Agent.

Combines:
  1. Detection engine (deterministic rules)
     - Lease underpricing + expiry risk
     - AP anomalies (duplicates, spikes)
     - AR collection risk
     - GL anomalies
  2. LLM reasoning layer (explain + recommend)
  3. Structured findings output
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from detection.detection_engine import (
    run_detection,
    load_leases,
    load_market_rates,
    load_ap_transactions,
    RawFinding,
)
from detection.ap_ar_gl import (
    load_ar_transactions,
    load_gl_entries,
    detect_ar_collection_risk,
    detect_ap_double_payments,
    detect_gl_anomalies,
)
from detection.ap_extended import run_ap_extended
from reasoning.llm_reasoning import enrich_findings


def hermes_agent(
    data_dir: str = None,
    use_llm: bool = True,
) -> list[dict]:
    """
    Main Hermes agent loop — runs all detection layers.

    Args:
        data_dir:        Path to data/ directory (default: <project>/data/)
        use_llm:         Whether to call LLM for reasoning (disable for pure rule demo)
    Returns:
        List of enriched finding dictionaries
    """
    if data_dir is None:
        data_dir = Path(__file__).parent / "data"

    lease_path     = Path(data_dir) / "sample_leases.csv"
    ap_path        = Path(data_dir) / "sample_ap.csv"
    ar_path        = Path(data_dir) / "sample_ar.csv"
    market_path    = Path(data_dir) / "market_benchmarks.csv"
    gl_path        = Path(data_dir) / "sample_gl.csv"

    print("\n🧠 HERMES ENTERPRISE INTELLIGENCE ENGINE")
    print("=" * 50)
    print()

    # ── Stage 1: Core detection (lease + AP from detection_engine) ────
    print("📊 Stage 1: Core detection rules (lease + AP)...")
    t0 = time.time()
    raw_findings: list[RawFinding] = run_detection(
        str(lease_path), str(ap_path), str(market_path)
    )
    print(f"   → {len(raw_findings)} findings from core engine")
    print()

    # ── Stage 2: AR collection risk ───────────────────────────────────
    print("📊 Stage 2: AR collection risk detection...")
    t1 = time.time()
    if ar_path.exists():
        ar_txns = load_ar_transactions(str(ar_path))
        ar_findings = detect_ar_collection_risk(ar_txns)
        raw_findings.extend(ar_findings)
        print(f"   → {len(ar_findings)} AR findings")
    else:
        print("   → No AR data found, skipping")
    print()

    # ── Stage 3: AP extended detection ─────────────────────────────────
    print("📊 Stage 3: AP extended detection...")
    t2 = time.time()
    if ap_path.exists():
        ap_txns = load_ap_transactions(str(ap_path))
        ap_findings = detect_ap_double_payments(ap_txns)
        ap_ext_findings = run_ap_extended(str(ap_path))
        raw_findings.extend(ap_findings)
        raw_findings.extend(ap_ext_findings)
        print(f"   → {len(ap_findings)} AP duplicate findings + {len(ap_ext_findings)} extended AP findings")
    else:
        print("   → No AP data found, skipping")
    print()

    # ── Stage 4: GL anomaly detection ─────────────────────────────────
    print("📊 Stage 4: GL anomaly detection...")
    t3 = time.time()
    if gl_path.exists():
        gl_entries = load_gl_entries(str(gl_path))
        gl_findings = detect_gl_anomalies(gl_entries)
        raw_findings.extend(gl_findings)
        print(f"   → {len(gl_findings)} GL findings")
    else:
        print("   → No GL data found, skipping")
    print()

    total_time = time.time() - t0
    print(f"✅ Detection complete: {len(raw_findings)} total findings in {total_time:.1f}s")
    for f in raw_findings:
        print(f"   [{f.type}] {f.entity} — ${abs(f.raw_impact):,.0f}")
    print()

    # ── Stage 5: LLM Enrichment ───────────────────────────────────────
    if use_llm:
        print("🤖 Stage 5: LLM reasoning + recommendations...")
        t_llm = time.time()
        enriched = enrich_findings([f.__dict__ for f in raw_findings])
        print(f"   → {len(enriched)} findings enriched in {time.time()-t_llm:.1f}s")
    else:
        print("⚡ Stage 5: Skipping LLM (demo mode — deterministic only)")
        enriched = [
            {
                "type": f.type,
                "entity": f.entity,
                "entity_id": f.entity_id,
                "issue": f.issue,
                "financial_impact": f"${abs(f.raw_impact):,.0f}",
                "confidence": "70%",
                "evidence": f.evidence,
                "explanation": "(LLM disabled — set GROQ_API_KEY or ANTHROPIC_API_KEY to enable)",
                "recommendation": "Add API key to enable AI recommendations",
                "expected_outcome": "N/A",
                "urgency": "Medium",
                "owner": "Finance Team",
                "jde_sources": f.jde_sources,
            }
            for f in raw_findings
        ]

    print()
    return enriched


def print_findings(findings: list[dict]):
    """Pretty-print findings for console output."""
    for i, f in enumerate(findings, 1):
        print(f"─── Finding {i} ───────────────────────────────")
        print(f"  🔴 Type:      {f['type']}")
        print(f"  🏢 Entity:    {f['entity']} [{f['entity_id']}]")
        print(f"  ⚠️  Issue:     {f['issue']}")
        print(f"  💰 Impact:    {f['financial_impact']}")
        print(f"  📊 Confidence: {f['confidence']}")
        print(f"  ⚡ Urgency:   {f['urgency']}")
        print(f"  👤 Owner:     {f['owner']}")
        print(f"  📚 Sources:   {', '.join(f['jde_sources'])}")
        print(f"  💡 Evidence:  {' | '.join(f['evidence'][:3])}")
        if f.get("explanation"):
            print(f"  🧠 Explanation: {f['explanation'][:120]}...")
        if f.get("recommendation"):
            print(f"  ✅ Action:    {f['recommendation']}")
        print()


if __name__ == "__main__":
    import os

    data_dir = Path(__file__).parent / "data"
    use_llm = not os.environ.get("DEMO_MODE", "").lower() in ("1", "true")

    findings = hermes_agent(
        data_dir=str(data_dir),
        use_llm=use_llm,
    )

    print()
    print_findings(findings)

    # Save output
    out_path = Path(__file__).parent / "output" / "findings.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(findings, f, indent=2, default=str)
    print(f"💾 Findings saved to: {out_path}")
