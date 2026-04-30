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
from dataclasses import dataclass


LLM_SYSTEM_PROMPT = """You are a senior financial analyst working for an enterprise asset management firm.
Your role is to explain financial findings in plain business language and provide clear, actionable recommendations.

Rules:
- Be direct and concise — executives read these quickly
- Always quantify financial impact in dollar terms
- Every recommendation must have a clear next action
- Flag urgency appropriately: High (< 30 days), Medium (30-90 days), Low (> 90 days)
- Do not speculate — only use the evidence provided
- If the evidence is insufficient to make a determination, say so
"""


def build_explain_prompt(finding: dict) -> str:
    return f"""Explain this financial finding in simple, direct business language.

Finding:
- Type: {finding['type']}
- Entity: {finding['entity']}
- Issue: {finding['issue']}
- Evidence: {', '.join(finding['evidence'])}
- Raw financial impact: ${abs(finding['raw_impact']):,.2f}{' potential loss' if finding['raw_impact'] > 0 else ' overpayment'}

Provide:
1. Plain-English summary (2 sentences max)
2. Why this matters to the business (1 sentence)
3. Key evidence supporting this finding (bullet points)
"""


def build_recommend_prompt(finding: dict) -> str:
    return f"""Based on this financial finding, provide a clear, actionable recommendation.

Finding:
- Type: {finding['type']}
- Entity: {finding['entity']}
- Issue: {finding['issue']}
- Evidence: {', '.join(finding['evidence'])}
- Raw financial impact: ${abs(finding['raw_impact']):,.2f}{' potential loss' if finding['raw_impact'] > 0 else ' overpayment'}

Output a JSON object with exactly this structure:
{{
  "action": "What to do (imperative, specific)",
  "expected_outcome": "What success looks like",
  "urgency": "High|Medium|Low",
  "owner": "Who should handle this (Finance / Asset Manager / Legal / etc.)"
}}
"""


def call_llm(prompt: str, model: str = "auto") -> str:
    """Call the configured LLM. Supports Groq, Anthropic, or OpenAI. Falls back to mock."""
    # Check Groq first (fastest, cheapest)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        return _call_groq(prompt, groq_key)

    # Check Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        return _call_anthropic(prompt, anthropic_key)

    # Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return _call_openai(prompt, openai_key)

    return _mock_llm_response(prompt)


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
        max_tokens=1024,
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
        max_tokens=1024,
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
        max_tokens=1024,
        temperature=0.3,
    )
    return response.choices[0].message.content


def _mock_llm_response(prompt: str) -> str:
    """Deterministic mock responses for demo mode."""
    if "recommend" in prompt.lower() or "action" in prompt.lower():
        return json.dumps({
            "action": "Review lease file and initiate renegotiation discussion with tenant",
            "expected_outcome": "Align rent to market rate at next renewal or sooner if break clause available",
            "urgency": "High",
            "owner": "Asset Manager"
        })
    elif "explain" in prompt.lower():
        return "This lease is being rented significantly below current market rates for comparable properties in the same location. The tenant is benefiting from a favourable deal while the portfolio is underperforming. Rectifying this gap would improve portfolio income materially."
    return "Unable to generate explanation."


def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response."""
    # Try to find JSON block
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Try whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def enrich_finding(finding: dict) -> dict:
    """Enrich a raw finding with LLM explanation and recommendation."""
    # Build prompts
    explain_prompt = build_explain_prompt(finding)
    recommend_prompt = build_recommend_prompt(finding)

    # Call LLM (or mock)
    explanation = call_llm(explain_prompt)
    recommendation_text = call_llm(recommend_prompt)

    # Parse recommendation JSON
    rec_data = extract_json(recommendation_text)

    # Calculate confidence based on evidence quality
    evidence_count = len(finding.get("evidence", []))
    confidence = min(0.95, 0.60 + (evidence_count * 0.07))

    # Determine urgency from raw finding type
    urgency = "Medium"
    if finding["type"] in ("Lease Expiry — Already Expired", "Duplicate Payment Risk"):
        urgency = "High"
    elif "Expiring Soon" in finding.get("status", "") or "Expired" in finding.get("status", ""):
        urgency = "High"
    elif finding["type"] == "Vendor Payment Spike":
        urgency = "Medium"

    if rec_data and rec_data.get("urgency"):
        urgency = rec_data["urgency"]

    # Format financial impact
    raw = abs(finding["raw_impact"])
    if raw >= 1_000_000:
        impact_str = f"${raw/1_000_000:.1f}M"
    elif raw >= 1_000:
        impact_str = f"${raw/1_000:.0f}K"
    else:
        impact_str = f"${raw:,.2f}"

    if finding["type"] in ("Lease Underpricing", "Lease Expiry — Already Expired", "Lease Expiry Risk"):
        impact_str += " annual upside at risk"
    elif "Duplicate" in finding["type"]:
        impact_str += " potential duplicate payment"
    elif "Spike" in finding["type"]:
        impact_str += " above median"

    return {
        "type": finding["type"],
        "entity": finding["entity"],
        "entity_id": finding["entity_id"],
        "issue": finding["issue"],
        "financial_impact": impact_str,
        "confidence": f"{confidence:.0%}",
        "evidence": finding.get("evidence", []),
        "explanation": explanation,
        "recommendation": rec_data.get("action", "Review and act on this finding") if rec_data else "Review and act on this finding",
        "expected_outcome": rec_data.get("expected_outcome", "Reduce financial risk") if rec_data else "Reduce financial risk",
        "urgency": urgency,
        "owner": rec_data.get("owner", "Finance Team") if rec_data else "Finance Team",
        "jde_sources": finding.get("jde_sources", []),
    }


def enrich_findings(raw_findings: list[dict]) -> list[dict]:
    """Enrich all findings. Returns enriched list."""
    return [enrich_finding(f) for f in raw_findings]
