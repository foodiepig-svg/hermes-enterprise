"""Extended AP detection: vendor concentration, payment timing, contract vs invoice."""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from detection.detection_engine import RawFinding, APTransaction, load_ap_transactions


def detect_vendor_concentration(txns: list[APTransaction]) -> list[RawFinding]:
    """Flag vendors with excessive spend concentration (>40% of total AP)."""
    findings = []

    # Group by vendor
    vendor_spend: dict[str, float] = defaultdict(float)
    vendor_txns: dict[str, list] = defaultdict(list)
    total_spend = 0.0
    for t in txns:
        if t.status == "Paid":
            vendor_spend[t.vendor_id] += t.amount
            vendor_txns[t.vendor_id].append(t)
            total_spend += t.amount

    if total_spend == 0:
        return findings

    threshold = total_spend * 0.40  # 40% concentration threshold
    for vendor_id, spend in vendor_spend.items():
        if spend >= threshold:
            txns_list = vendor_txns[vendor_id]
            findings.append(RawFinding(
                type="AP — Vendor Concentration Risk",
                entity=txns_list[0].vendor_name,
                entity_id=vendor_id,
                issue=f"Vendor {txns_list[0].vendor_name} accounts for {spend/total_spend:.0%} of total AP spend (${spend:,.2f} of ${total_spend:,.2f}) — concentration risk",
                evidence=[
                    f"Total paid to {vendor_id}: ${spend:,.2f}",
                    f"Total AP spend: ${total_spend:,.2f}",
                    f"Concentration: {spend/total_spend:.1%}",
                    f"Number of invoices: {len(txns_list)}",
                    f"GL account: {txns_list[0].gl_account}",
                ],
                raw_impact=spend * 0.10,  # Estimated risk if vendor fails/overcharges
                jde_sources=["F0411 (Accounts Payable)", f"GL: {txns_list[0].gl_account}"],
            ))

    return findings


def detect_payment_timing_anomalies(txns: list[APTransaction]) -> list[RawFinding]:
    """Flag invoices paid after due date (late) or suspiciously early (related party risk)."""
    findings = []

    for t in txns:
        if t.status != "Paid" or not t.payment_date:
            continue

        days_early = (t.due_date - t.payment_date).days
        days_late = (t.payment_date - t.due_date).days

        # Late payment (>14 days past due)
        if days_late > 14:
            findings.append(RawFinding(
                type="AP — Late Payment",
                entity=t.vendor_name,
                entity_id=t.invoice_id,
                issue=f"Invoice {t.invoice_id} paid {days_late} days late (due: {t.due_date.strftime('%d %b %Y')}, paid: {t.payment_date.strftime('%d %b %Y')}) — ${t.amount:,.2f}",
                evidence=[
                    f"F0411 invoice {t.invoice_id} = ${t.amount:,.2f}",
                    f"Due date: {t.due_date.strftime('%d %b %Y')}",
                    f"Payment date: {t.payment_date.strftime('%d %b %Y')}",
                    f"Days late: {days_late}",
                    f"GL: {t.gl_account}",
                ],
                raw_impact=t.amount * 0.05,  # Late fees / relationship risk
                jde_sources=["F0411 (Accounts Payable)"],
            ))

        # Suspiciously early payment (<3 days before due — potential kickback/related party)
        if days_early in range(1, 3) and t.amount >= 5000:
            findings.append(RawFinding(
                type="AP — Suspiciously Early Payment",
                entity=t.vendor_name,
                entity_id=t.invoice_id,
                issue=f"Invoice {t.invoice_id} paid {days_early} days before due — ${t.amount:,.2f} to {t.vendor_name}. Unusual timing may indicate related-party arrangement.",
                evidence=[
                    f"F0411 invoice {t.invoice_id} = ${t.amount:,.2f}",
                    f"Due date: {t.due_date.strftime('%d %b %Y')}",
                    f"Payment date: {t.payment_date.strftime('%d %b %Y')}",
                    f"Days early: {days_early}",
                    f"Amount: ${t.amount:,.2f}",
                ],
                raw_impact=t.amount * 0.02,
                jde_sources=["F0411 (Accounts Payable)"],
            ))

    return findings


def detect_payment_term_changes(txns: list[APTransaction]) -> list[RawFinding]:
    """Detect vendors whose average payment terms have shifted significantly."""
    findings = []

    # Group by vendor
    vendor_terms: dict[str, list] = defaultdict(list)
    for t in txns:
        if t.status == "Paid" and t.payment_date:
            days_to_pay = (t.payment_date - t.invoice_date).days
            vendor_terms[t.vendor_id].append((days_to_pay, t.amount, t))

    for vendor_id, terms in vendor_terms.items():
        if len(terms) < 3:
            continue

        # Sort by date and compare first half vs second half average
        terms.sort(key=lambda x: x[2].invoice_date)
        mid = len(terms) // 2
        first_half_avg = sum(t[0] for t in terms[:mid]) / mid
        second_half_avg = sum(t[0] for t in terms[mid:]) / (len(terms) - mid)
        shift = second_half_avg - first_half_avg

        if abs(shift) > 10:  # >10 day shift
            direction = "longer" if shift > 0 else "shorter"
            findings.append(RawFinding(
                type="AP — Payment Term Shift",
                entity=terms[0][2].vendor_name,
                entity_id=vendor_id,
                issue=f"Vendor {terms[0][2].vendor_name} payment terms shifted {abs(shift):.0f} days {direction} — avg now {second_half_avg:.0f} days from invoice to payment",
                evidence=[
                    f"First half avg payment term: {first_half_avg:.0f} days",
                    f"Second half avg payment term: {second_half_avg:.0f} days",
                    f"Shift: {abs(shift):.0f} days {direction}",
                    f"Invoices analysed: {len(terms)}",
                    f"Total spend: ${sum(t[1] for t in terms):,.2f}",
                ],
                raw_impact=sum(t[1] for t in terms) * 0.03,
                jde_sources=["F0411 (Accounts Payable)"],
            ))

    return findings


def run_ap_extended(ap_path: str) -> list[RawFinding]:
    txns = load_ap_transactions(ap_path)
    findings = []
    findings.extend(detect_vendor_concentration(txns))
    findings.extend(detect_payment_timing_anomalies(txns))
    findings.extend(detect_payment_term_changes(txns))
    return findings
