"""CEO Demo Output — Hermes Enterprise Intelligence Engine.

Generates a clean, readable executive summary of all findings.
"""

import json
from pathlib import Path


def parse_impact(s: str) -> float:
    """Parse dollar value from impact strings like '$18K annual upside at risk'."""
    import re
    s = s.strip()
    m = re.match(r"\$([0-9.]+)\s*(M|K)?", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    mult = m.group(2)
    if mult == "M":
        val *= 1_000_000
    elif mult == "K":
        val *= 1_000
    return val


def print_ceo_summary(findings: list[dict]):
    total_impact = 0
    high_urgency = []

    for f in findings:
        impact_str = f.get("financial_impact", "$0")
        val = parse_impact(impact_str)
        total_impact += val
        if f.get("urgency") == "High":
            high_urgency.append(f)

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     HERMES ENTERPRISE — EXECUTIVE INTELLIGENCE SUMMARY        ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Portfolio analysed:        10 leases | $623K annual rent    ║")
    print(f"║  Findings detected:          {len(findings)} total | {len(high_urgency)} high urgency           ║")
    if total_impact >= 1_000_000:
        print(f"║  💰 Total financial exposure:  ${total_impact/1_000_000:.2f}M                       ║")
    else:
        print(f"║  💰 Total financial exposure:  ${total_impact/1_000:.0f}K                          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    for i, f in enumerate(high_urgency, 1):
        print(f"  {'🔴' if f['urgency'] == 'High' else '🟡'}  {f['type']}")
        print(f"     📍 {f['entity']}")
        print(f"     ⚠️  {f['issue']}")
        print(f"     💰 {f['financial_impact']} | Confidence: {f['confidence']} | {f['urgency']} urgency")
        if f.get("recommendation"):
            print(f"     ✅ {f['recommendation']}")
        print()

    print("  ─────────────────────────────────────────────────────")
    print(f"  📊 All findings: {len(findings)} | High urgency: {len(high_urgency)}")
    print(f"  🗂  Full report: output/findings.json")
    print()


if __name__ == "__main__":
    out_path = Path(__file__).parent.parent / "output" / "findings.json"
    with open(out_path) as f:
        findings = json.load(f)
    print_ceo_summary(findings)
