"""LLM reasoning layer for Hermes Enterprise Intelligence Layer.

Enriches deterministic detection findings with:
- Plain-English explanation of the issue
- Actionable recommendation
- Confidence + urgency scoring

Deterministic first, AI second — LLM only handles narrative.
"""

import json
import os
import re
from typing import Any


LLM_SYSTEM_PROMPT = """You are a senior financial analyst working for an enterprise asset management firm.
Your role is to explain financial findings in plain business language and provide clear, actionable recommendations.

Rules:
- Be direct and concise — executives read these quickly
- Always quantify financial impact in dollar terms
- Every recommendation must have a clear next action
- Flag urgency appropriately: High (< 30 days), Medium (30-90 days), Low (> 90 days)
- Do not speculate — only use the evidence provided
- If the evidence is insufficient to make a determination, say so
- Output valid JSON only — no markdown, no preamble, no commentary
"""


def _format_impact(raw_impact: float, finding_type: str) -> str:
    """Format financial impact string from raw float."""
    abs_impact = abs(raw_impact)
    if abs_impact >= 1_000_000:
        impact_str = f"${abs_impact/1_000_000:.1f}M"
    elif abs_impact >= 1_000:
        impact_str = f"${abs_impact/1_000:.0f}K"
    else:
        impact_str = f"${abs_impact:,.2f}"

    if finding_type in ("Lease Underpricing", "Lease Expiry — Already Expired", "Lease Expiry Risk"):
        impact_str += " annual upside at risk"
    elif "Duplicate" in finding_type:
        impact_str += " potential duplicate payment"
    elif "Spike" in finding_type:
        impact_str += " above median"

    return impact_str


def _to_dict(finding) -> dict:
    """Convert a RawFinding dataclass or dict to a plain dict."""
    if isinstance(finding, dict):
        return finding
    # Handle dataclass-like objects (has __dataclass_fields__)
    if hasattr(finding, "__dataclass_fields__"):
        return {f: getattr(finding, f) for f in finding.__dataclass_fields__}
    return dict(finding)


def _build_base_finding(finding: dict) -> dict:
    """Build the base enriched finding dict from a raw finding dict or dataclass."""
    f = _to_dict(finding)
    raw_impact = abs(f.get("raw_impact", 0))
    finding_type = f.get("type", "Unknown")

    confidence = min(0.95, 0.60 + (len(f.get("evidence", [])) * 0.07))

    return {
        "type": finding_type,
        "entity": f.get("entity", "—"),
        "entity_id": f.get("entity_id", ""),
        "issue": f.get("issue", ""),
        "financial_impact": _format_impact(raw_impact, finding_type),
        "confidence": f"{confidence:.0%}",
        "evidence": f.get("evidence", []),
        "jde_sources": f.get("jde_sources", []),
    }


def _extract_json_array(text: str) -> list | None:
    """Extract a JSON array from LLM response text."""
    text = text.strip()
    # Try direct JSON parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    # Try to find array bounds
    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1:
        try:
            return json.loads(text[arr_start:arr_end+1])
        except json.JSONDecodeError:
            pass
    return None


def _parse_enrichment(data: dict, base: dict) -> dict:
    """Parse LLM enrichment data into the base finding."""
    result = base.copy()
    result["explanation"] = data.get("explanation", "No explanation generated.")
    result["recommendation"] = data.get("recommendation", data.get("action", "Review and act on this finding."))
    result["expected_outcome"] = data.get("expected_outcome", "Reduce financial risk.")
    result["urgency"] = data.get("urgency", "Medium")
    result["owner"] = data.get("owner", "Finance Team")
    return result


# ─── Provider calls ───────────────────────────────────────────────────────────

def _call_groq(prompt: str, api_key: str) -> str:
    """Call Groq API (fast, cheap, supports Llama/Mixtral)."""
    import groq

    client = groq.Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    return response.choices[0].message.content


def _call_anthropic(prompt: str, api_key: str) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    api_base = os.environ.get("ANTHROPIC_API_BASE", "").strip()
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=api_base if api_base else None,
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=LLM_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(prompt: str, api_key: str) -> str:
    """Call OpenAI GPT API."""
    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    return response.choices[0].message.content


def _mock_batch_enrichment(raw_findings: list[dict]) -> list[dict]:
    """Deterministic mock for demo / no API key."""
    results = []
    for finding in raw_findings:
        f = _to_dict(finding)
        base = _build_base_finding(f)
        finding_type = f.get("type", "")
        entity = f.get("entity", "this entity")

        if "lease" in finding_type.lower():
            explanation = f"{entity} shows a significant deviation from market-rate benchmarks. The current arrangement appears unfavourable relative to comparable properties in the same location and asset class."
            recommendation = f"Arrange a portfolio review meeting with the tenant 90 days before lease expiry. Target market-rate alignment at renewal, supported by a formal rent Comparable analysis."
        elif "duplicate" in finding_type.lower():
            explanation = f"A payment matching {entity} was identified. The payment profile suggests a possible duplicate that warrants immediate reconciliation review."
            recommendation = f"Freeze payment run for this vendor. Finance team to reconcile {entity} against prior periods within 48 hours before any further payments are approved."
        elif "ar" in finding_type.lower() or "collection" in finding_type.lower():
            explanation = f"{entity} has invoices that are significantly overdue. Extended delays in collection erode working capital and may signal broader customer distress."
            recommendation = f"Initiate a formal collections process. Escalate to senior management if payment is not received within 14 days."
        elif "vendor" in finding_type.lower() or "concentration" in finding_type.lower():
            explanation = f"{entity} represents a disproportionate share of total AP spend. Concentration risk increases exposure to supply chain disruption if this vendor encounters financial difficulty."
            recommendation = f"Diversify vendor relationships where possible. Review the commercial rationale for concentration and assess whether contractual protections are in place."
        elif "early" in finding_type.lower() or "payment" in finding_type.lower():
            explanation = f"{entity} was paid ahead of schedule. Early payments may indicate manual overrides in the accounts payable workflow and could represent missed float benefits."
            recommendation = f"Review the payment approval workflow for this vendor. Confirm whether early payments are intentional or indicate a process deviation."
        else:
            explanation = f"{entity} was flagged by the detection engine. Further investigation is recommended to determine root cause and appropriate action."
            recommendation = "Review the finding in the Hermes dashboard. Escalate to the appropriate team based on the finding type."

        result = base.copy()
        result["explanation"] = explanation
        result["recommendation"] = recommendation
        result["expected_outcome"] = "Reduce financial risk and improve operational efficiency."
        result["urgency"] = "High" if "duplicate" in finding_type.lower() else "Medium"
        result["owner"] = "Finance Team"
        results.append(result)

    return results


def _build_batch_prompt(raw_findings: list[dict]) -> str:
    """Build a single LLM prompt containing all raw findings."""
    findings_text = []
    for i, finding in enumerate(raw_findings, 1):
        f = _to_dict(finding)
        findings_text.append(f"""Finding {i}:
  Type: {f.get('type', 'Unknown')}
  Entity: {f.get('entity', '—')}
  Issue: {f.get('issue', '—')}
  Evidence: {', '.join(f.get('evidence', []) or ['No evidence'])}
  Financial impact: ${abs(f.get('raw_impact', 0)):,.2f}
  JDE Sources: {', '.join(f.get('jde_sources', []) or ['None'])}""")

    findings_block = "\n\n".join(findings_text)

    return f"""You are processing {len(raw_findings)} financial findings from an enterprise intelligence engine.

For EACH finding, generate an enrichment with exactly these fields:
- explanation: Plain-English description (2-3 sentences) explaining what this finding means and why it matters
- recommendation: Specific, actionable next step (1-2 sentences, imperative mood)
- urgency: High / Medium / Low — based on financial impact and time sensitivity
- owner: Which team should own this (e.g. Finance Team, Asset Manager, Legal, Operations)

Return a JSON array with {len(raw_findings)} objects — one per finding, in the same order as provided.
Each object must have: explanation, recommendation, urgency, owner

Do not include any text outside the JSON array.

Findings:
{findings_block}
"""


def _call_llm_batch(prompt: str) -> str | None:
    """Call the configured LLM for batch enrichment. Returns raw response or None."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key and groq_key not in ("", "[REDACTED]", "YOUR_KEY_HERE"):
        try:
            return _call_groq(prompt, groq_key)
        except Exception as e:
            print(f"[LLM] Groq call failed ({e}). Trying next provider...")

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key and anthropic_key not in ("", "[REDACTED]", "YOUR_KEY_HERE"):
        try:
            return _call_anthropic(prompt, anthropic_key)
        except Exception as e:
            print(f"[LLM] Anthropic call failed ({e}). Trying next provider...")

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key and openai_key not in ("", "[REDACTED]", "YOUR_KEY_HERE"):
        try:
            return _call_openai(prompt, openai_key)
        except Exception as e:
            print(f"[LLM] OpenAI call failed ({e}).")

    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def enrich_findings(raw_findings: list[dict]) -> list[dict]:
    """
    Enrich all raw findings with LLM-generated explanation and recommendations.

    Uses BATCH processing — all findings sent in a single LLM call for speed.
    Falls back to mock enrichment if no API key is configured.

    Args:
        raw_findings: List of raw finding dicts from detection layer.
                     Each should have: type, entity, entity_id, issue, evidence,
                     raw_impact, jde_sources.

    Returns:
        List of enriched finding dicts with explanation, recommendation,
        urgency, owner, expected_outcome fields added.
    """
    if not raw_findings:
        return []

    # Build base findings (without LLM content) for all items
    base_findings = [_build_base_finding(f) for f in raw_findings]

    # Try batch LLM call
    prompt = _build_batch_prompt(raw_findings)
    response = _call_llm_batch(prompt)

    if response:
        enrichment_data = _extract_json_array(response)
        if enrichment_data and len(enrichment_data) == len(raw_findings):
            return [
                _parse_enrichment(enrichment_data[i], base_findings[i])
                for i in range(len(raw_findings))
            ]
        else:
            print(f"[LLM] Failed to parse batch response ({len(enrichment_data) if enrichment_data else 0} items, expected {len(raw_findings)}). Falling back to mock.")
    else:
        print("[LLM] No API key configured. Using mock enrichment.")

    # Fallback: mock enrichment
    return _mock_batch_enrichment(raw_findings)


# ─── Single-finding enrichment (kept for backward compatibility) ───────────────

def enrich_finding(finding: dict) -> dict:
    """Enrich a single finding. Wrapper around enrich_findings for backward compat."""
    return enrich_findings([finding])[0]
