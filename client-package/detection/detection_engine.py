"""Detection engine for Hermes Enterprise Intelligence Layer."""

import csv
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class Lease:
    lease_id: str
    property_id: str
    property_name: str
    location: str
    tenant: str
    asset_type: str
    area_sqm: float
    lease_start: date
    lease_end: date
    rent_per_sqm: float
    annual_rent: float
    escalation_pct: float
    status: str


@dataclass
class APTransaction:
    invoice_id: str
    vendor_id: str
    vendor_name: str
    invoice_date: date
    due_date: date
    amount: float
    status: str
    payment_date: Optional[date]
    description: str
    gl_account: str


@dataclass
class MarketRate:
    location: str
    asset_type: str
    market_rate_sqm: float
    benchmark_date: date
    data_source: str


@dataclass
class RawFinding:
    """Deterministic detection output — before LLM enrichment."""
    type: str
    entity: str
    entity_id: str
    issue: str
    evidence: list[str]
    raw_impact: float
    jde_sources: list[str]


@dataclass
class EnrichedFinding:
    """LLM-enriched finding with reasoning and recommendations."""
    type: str
    entity: str
    entity_id: str
    issue: str
    financial_impact: str
    confidence: float
    evidence: list[str]
    explanation: str
    recommendation: str
    urgency: str
    jde_sources: list[str]


# ─── Load helpers ─────────────────────────────────────────────────────────────

def load_leases(path: str) -> list[Lease]:
    leases = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            leases.append(Lease(
                lease_id=row["lease_id"],
                property_id=row["property_id"],
                property_name=row["property_name"],
                location=row["location"],
                tenant=row["tenant"],
                asset_type=row["asset_type"],
                area_sqm=float(row["area_sqm"]),
                lease_start=datetime.strptime(row["lease_start"], "%Y-%m-%d").date(),
                lease_end=datetime.strptime(row["lease_end"], "%Y-%m-%d").date(),
                rent_per_sqm=float(row["rent_per_sqm"]),
                annual_rent=float(row["annual_rent"]),
                escalation_pct=float(row["escalation_pct"]),
                status=row["status"],
            ))
    return leases


def load_ap_transactions(path: str) -> list[APTransaction]:
    txns = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            payment_date = None
            if row["payment_date"]:
                payment_date = datetime.strptime(row["payment_date"], "%Y-%m-%d").date()
            txns.append(APTransaction(
                invoice_id=row["invoice_id"],
                vendor_id=row["vendor_id"],
                vendor_name=row["vendor_name"],
                invoice_date=datetime.strptime(row["invoice_date"], "%Y-%m-%d").date(),
                due_date=datetime.strptime(row["due_date"], "%Y-%m-%d").date(),
                amount=float(row["amount"]),
                status=row["status"],
                payment_date=payment_date,
                description=row["description"],
                gl_account=row["gl_account"],
            ))
    return txns


def load_market_rates(path: str) -> dict[tuple[str, str], MarketRate]:
    rates = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["location"], row["asset_type"])
            rates[key] = MarketRate(
                location=row["location"],
                asset_type=row["asset_type"],
                market_rate_sqm=float(row["market_rate_sqm"]),
                benchmark_date=datetime.strptime(row["benchmark_date"], "%Y-%m-%d").date(),
                data_source=row["data_source"],
            )
    return rates


# ─── Detection: Lease underpricing ────────────────────────────────────────────

def detect_lease_opportunities(leases: list[Lease], market: dict) -> list[RawFinding]:
    """Detect leases rented more than 10% below market rate."""
    findings = []
    today = date.today()

    for lease in leases:
        # Only check active leases
        if lease.status != "Active":
            continue

        market_key = (lease.location, lease.asset_type)
        if market_key not in market:
            continue

        market_rate = market[market_key].market_rate_sqm
        gap_pct = (market_rate - lease.rent_per_sqm) / market_rate

        if gap_pct > 0.10:  # More than 10% below market
            annual_gap = (market_rate - lease.rent_per_sqm) * lease.area_sqm
            findings.append(RawFinding(
                type="Lease Underpricing",
                entity=lease.property_name,
                entity_id=lease.lease_id,
                issue=f"Rent is {gap_pct:.1%} below market benchmark (${lease.rent_per_sqm:.2f}/sqm vs ${market_rate:.2f}/sqm market)",
                evidence=[
                    f"F1501 lease rate = ${lease.rent_per_sqm:.2f}/sqm",
                    f"Market benchmark ({lease.asset_type}, {lease.location}) = ${market_rate:.2f}/sqm",
                    f"Lease area = {lease.area_sqm:.0f} sqm",
                    f"Annual rent = ${lease.annual_rent:,.2f}",
                ],
                raw_impact=annual_gap,
                jde_sources=["F1501 (Lease Master)", "F1502 (Lease Terms)"],
            ))

    return findings


# ─── Detection: Lease expiry risk ─────────────────────────────────────────────

def detect_lease_expiry_risk(leases: list[Lease]) -> list[RawFinding]:
    """Detect leases expiring within 6 months."""
    findings = []
    today = date.today()

    for lease in leases:
        days_to_expiry = (lease.lease_end - today).days

        if 0 < days_to_expiry <= 180:  # Expiring within 6 months
            findings.append(RawFinding(
                type="Lease Expiry Risk",
                entity=lease.property_name,
                entity_id=lease.lease_id,
                issue=f"Lease expires in {days_to_expiry} days ({lease.lease_end.strftime('%d %b %Y')}) — renegotiation window open",
                evidence=[
                    f"F1501 lease_end = {lease.lease_end.strftime('%Y-%m-%d')}",
                    f"Current rent = ${lease.rent_per_sqm:.2f}/sqm",
                    f"Annual rent = ${lease.annual_rent:,.2f}",
                    f"Status = {lease.status}",
                ],
                raw_impact=lease.annual_rent,  # At-risk revenue
                jde_sources=["F1501 (Lease Master)"],
            ))
        elif days_to_expiry <= 0 and lease.status == "Active":
            findings.append(RawFinding(
                type="Lease Expiry — Already Expired",
                entity=lease.property_name,
                entity_id=lease.lease_id,
                issue=f"Lease expired on {lease.lease_end.strftime('%d %b %Y')} — still recorded as Active",
                evidence=[
                    f"F1501 lease_end = {lease.lease_end.strftime('%Y-%m-%d')}",
                    f"F1501 status = Active (should be reviewed)",
                    f"Annual rent at risk = ${lease.annual_rent:,.2f}",
                ],
                raw_impact=lease.annual_rent,
                jde_sources=["F1501 (Lease Master)"],
            ))

    return findings


# ─── Detection: AP duplicate / anomaly ────────────────────────────────────────

def detect_ap_anomalies(txns: list[APTransaction]) -> list[RawFinding]:
    """Detect duplicate or suspicious payments to the same vendor."""
    findings = []

    # Group by vendor + description (same service = potential duplicate)
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for t in txns:
        if t.status == "Paid":
            key = (t.vendor_id, t.description)
            groups[key].append(t)

    for (vendor_id, description), items in groups.items():
        if len(items) < 2:
            continue

        # Check for same amount within 7 days
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                t1, t2 = items[i], items[j]
                days_diff = abs((t2.invoice_date - t1.invoice_date).days)
                if days_diff <= 7 and abs(t1.amount - t2.amount) < 1.0:
                    duplicate_amount = min(t1.amount, t2.amount)
                    findings.append(RawFinding(
                        type="Duplicate Payment Risk",
                        entity=t1.vendor_name,
                        entity_id=t1.invoice_id,
                        issue=f"Duplicate invoices ({t1.invoice_id} and {t2.invoice_id}) — both paid ${duplicate_amount:,.2f}",
                        evidence=[
                            f"F0411 invoice {t1.invoice_id} = ${t1.amount:,.2f} on {t1.invoice_date}",
                            f"F0411 invoice {t2.invoice_id} = ${t2.amount:,.2f} on {t2.invoice_date}",
                            f"Invoice dates differ by {days_diff} days",
                            f"Both coded to GL {t1.gl_account}",
                        ],
                        raw_impact=duplicate_amount,
                        jde_sources=["F0411 (Accounts Payable)", f"GL: {t1.gl_account}"],
                    ))

    # Check for vendor payment spikes (>50% above median)
    vendor_amounts: dict[str, list[float]] = defaultdict(list)
    for t in txns:
        vendor_amounts[t.vendor_id].append(t.amount)

    for vendor_id, amounts in vendor_amounts.items():
        if len(amounts) < 3:
            continue
        median = sorted(amounts)[len(amounts) // 2]
        for t in txns:
            if t.vendor_id == vendor_id and t.amount > median * 1.5:
                findings.append(RawFinding(
                    type="Vendor Payment Spike",
                    entity=t.vendor_name,
                    entity_id=t.invoice_id,
                    issue=f"Invoice {t.invoice_id} is ${t.amount:,.2f} — {((t.amount/median)-1):.1%} above vendor median (${median:,.2f})",
                    evidence=[
                        f"F0411 invoice {t.invoice_id} = ${t.amount:,.2f}",
                        f"Vendor {vendor_id} median = ${median:,.2f}",
                        f"Description: {t.description}",
                    ],
                    raw_impact=t.amount - median,
                    jde_sources=["F0411 (Accounts Payable)"],
                ))

    return findings


# ─── Master detection runner ─────────────────────────────────────────────────

def run_detection(lease_path: str, ap_path: str, market_path: str) -> list[RawFinding]:
    leases = load_leases(lease_path)
    ap_txns = load_ap_transactions(ap_path)
    market = load_market_rates(market_path)

    all_findings = []
    all_findings.extend(detect_lease_opportunities(leases, market))
    all_findings.extend(detect_lease_expiry_risk(leases))
    all_findings.extend(detect_ap_anomalies(ap_txns))

    return all_findings
