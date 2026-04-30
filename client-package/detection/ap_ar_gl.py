"""AR, GL, and extended AP detection modules for Hermes Enterprise."""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from detection.detection_engine import (
    RawFinding,
    load_ap_transactions,
    load_leases,
)


# ─── AR data model ─────────────────────────────────────────────────────────────

@dataclass
class ARTransaction:
    invoice_id: str
    customer_id: str
    customer_name: str
    invoice_date: date
    due_date: date
    amount: float
    status: str
    days_overdue: int
    last_payment_date: Optional[date]
    property_id: Optional[str]
    description: str


def load_ar_transactions(path: str) -> list[ARTransaction]:
    txns = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_pmt = None
            if row["last_payment_date"]:
                last_pmt = datetime.strptime(row["last_payment_date"], "%Y-%m-%d").date()
            days_overdue = int(row.get("days_overdue", "0") or "0")
            days_overdue = max(0, days_overdue)
            txns.append(ARTransaction(
                invoice_id=row["invoice_id"],
                customer_id=row["customer_id"],
                customer_name=row["customer_name"],
                invoice_date=datetime.strptime(row["invoice_date"], "%Y-%m-%d").date(),
                due_date=datetime.strptime(row["due_date"], "%Y-%m-%d").date(),
                amount=float(row["amount"]),
                status=row["status"],
                days_overdue=days_overdue,
                last_payment_date=last_pmt,
                property_id=row.get("property_id") or None,
                description=row["description"],
            ))
    return txns


# ─── GL data model ─────────────────────────────────────────────────────────────

@dataclass
class GLEntry:
    gl_account: str
    account_name: str
    company: str
    period: str
    amount: float
    doc_type: str
    doc_number: str
    vendor_id: Optional[str]
    description: str


def load_gl_entries(path: str) -> list[GLEntry]:
    entries = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(GLEntry(
                gl_account=row["gl_account"],
                account_name=row["account_name"],
                company=row["company"],
                period=row["period"],
                amount=float(row["amount"]),
                doc_type=row["doc_type"],
                doc_number=row["doc_number"],
                vendor_id=row.get("vendor_id") or None,
                description=row["description"],
            ))
    return entries


# ─── Detection: AR ageing / collection risk ─────────────────────────────────────

def detect_ar_collection_risk(txns: list[ARTransaction]) -> list[RawFinding]:
    """Detect overdue invoices, concentration risk, and payment pattern anomalies."""
    findings = []

    # 1. Critically overdue invoices (>60 days)
    for t in txns:
        if t.days_overdue > 60:
            findings.append(RawFinding(
                type="AR — Critical Overdue",
                entity=t.customer_name,
                entity_id=t.invoice_id,
                issue=f"Invoice {t.invoice_id} overdue by {t.days_overdue} days — ${t.amount:,.2f} uncollected",
                evidence=[
                    f"F03B11 invoice {t.invoice_id} = ${t.amount:,.2f}",
                    f"Due date: {t.due_date.strftime('%d %b %Y')}",
                    f"Days overdue: {t.days_overdue}",
                    f"Current status: {t.status}",
                    f"Description: {t.description}",
                ],
                raw_impact=t.amount,
                jde_sources=["F03B11 (Accounts Receivable)"],
            ))

    # 2. Customer payment pattern — increasing delinquency
    customer_invoices: dict[str, list[ARTransaction]] = defaultdict(list)
    for t in txns:
        customer_invoices[t.customer_id].append(t)

    for customer_id, invoices in customer_invoices.items():
        if len(invoices) < 3:
            continue
        overdue_pct = sum(1 for t in invoices if t.status == "Overdue") / len(invoices)
        total_owed = sum(t.amount for t in invoices if t.status in ("Overdue", "Pending"))
        if overdue_pct >= 0.5 and total_owed > 10000:
            findings.append(RawFinding(
                type="AR — Payment Pattern Delinquency",
                entity=invoices[0].customer_name,
                entity_id=customer_id,
                issue=f"Customer has {overdue_pct:.0%} of invoices overdue — ${total_owed:,.2f} outstanding",
                evidence=[
                    f"Total invoices: {len(invoices)}",
                    f"Overdue invoices: {sum(1 for t in invoices if t.status == 'Overdue')}",
                    f"Total outstanding: ${total_owed:,.2f}",
                    f"Customer since: {min(t.invoice_date for t in invoices).strftime('%d %b %Y')}",
                ],
                raw_impact=total_owed,
                jde_sources=["F03B11 (Accounts Receivable)"],
            ))

    # 3. Large outstanding invoice (>=$20K, >30 days overdue)
    for t in txns:
        if t.amount >= 20_000 and t.days_overdue >= 30:
            findings.append(RawFinding(
                type="AR — Large Outstanding Invoice",
                entity=t.customer_name,
                entity_id=t.invoice_id,
                issue=f"${t.amount:,.2f} invoice {t.invoice_id} overdue {t.days_overdue} days — significant collection risk",
                evidence=[
                    f"F03B11 amount = ${t.amount:,.2f}",
                    f"Days overdue = {t.days_overdue}",
                    f"Due date = {t.due_date.strftime('%d %b %Y')}",
                    f"Status = {t.status}",
                ],
                raw_impact=t.amount,
                jde_sources=["F03B11 (Accounts Receivable)"],
            ))

    return findings


# ─── Detection: AP extended anomalies ─────────────────────────────────────────

def detect_ap_double_payments(txns: list) -> list[RawFinding]:
    """Detect exact duplicate payments (same vendor, same amount, same period)."""
    findings = []

    # Group by vendor + amount (exact)
    from detection.detection_engine import APTransaction
    groups: dict[tuple, list] = defaultdict(list)
    for t in txns:
        key = (t.vendor_id, round(t.amount, 2))
        groups[key].append(t)

    for (vendor_id, amount), items in groups.items():
        if len(items) < 2:
            continue
        # Check if they're within same billing period (roughly same month)
        periods = set()
        for t in items:
            if t.invoice_date:
                periods.add((t.invoice_date.year, t.invoice_date.month))
        if len(periods) == 1 and len(items) >= 2:
            # Duplicate payment confirmed
            duplicate_amount = amount
            invoice_ids = [t.invoice_id for t in items]
            findings.append(RawFinding(
                type="AP — Duplicate Payment Confirmed",
                entity=items[0].vendor_name,
                entity_id=items[0].invoice_id,
                issue=f"Confirmed duplicate payments: {invoice_ids} — ${duplicate_amount:,.2f} paid twice to {items[0].vendor_name}",
                evidence=[
                    f"F0411 invoice IDs: {', '.join(invoice_ids)}",
                    f"Each = ${amount:,.2f}",
                    f"Both coded to GL {items[0].gl_account}",
                    f"Vendor: {items[0].vendor_name} ({vendor_id})",
                ],
                raw_impact=duplicate_amount,
                jde_sources=["F0411 (Accounts Payable)", f"GL: {items[0].gl_account}"],
            ))

    return findings


# ─── Detection: GL anomalies ──────────────────────────────────────────────────

def detect_gl_anomalies(entries: list[GLEntry]) -> list[RawFinding]:
    """Detect unusual GL entries: round amounts, duplicate postings, account misclassification."""
    findings = []

    # 1. Round number anomalies (round amounts > $10K are suspicious in expense categories)
    suspicious_accounts = {"6100", "6200", "6300", "6400", "6500", "6600"}  # Expense accounts
    for e in entries:
        if e.amount >= 10_000 and e.amount == round(e.amount):  # Exact round number
            if any(e.gl_account.startswith(acct) for acct in suspicious_accounts):
                findings.append(RawFinding(
                    type="GL — Round Number Anomaly",
                    entity=e.account_name,
                    entity_id=e.doc_number,
                    issue=f"Round expense amount ${e.amount:,.2f} posted to {e.gl_account} ({e.account_name}) — potential manual override or error",
                    evidence=[
                        f"F0911 {e.gl_account} = ${e.amount:,.2f}",
                        f"Doc type: {e.doc_type}, Doc number: {e.doc_number}",
                        f"Period: {e.period}",
                        f"Description: {e.description}",
                    ],
                    raw_impact=e.amount,
                    jde_sources=["F0911 (General Ledger)"],
                ))

    # 2. Duplicate GL postings (same account, same period, same amount)
    gl_groups: dict[tuple, list] = defaultdict(list)
    for e in entries:
        key = (e.gl_account, e.period, round(e.amount, 2))
        gl_groups[key].append(e)

    for key, items in gl_groups.items():
        if len(items) >= 2 and abs(items[0].amount) > 1000:
            gl_account, period, amount = key
            findings.append(RawFinding(
                type="GL — Duplicate Line Item",
                entity=items[0].account_name,
                entity_id=items[0].doc_number,
                issue=f"Duplicate postings to {gl_account} in period {period}: {len(items)} entries of ${amount:,.2f}",
                evidence=[
                    f"F0911 account {gl_account} = ${amount:,.2f}",
                    f"Period: {period}",
                    f"Doc numbers: {', '.join(set(i.doc_number for i in items))}",
                    f"Total duplicated: ${amount * len(items):,.2f}",
                ],
                raw_impact=amount * (len(items) - 1),
                jde_sources=["F0911 (General Ledger)"],
            ))

    # 3. Unusual journal type (non-PV, non-PY on expense accounts)
    normal_types = {"PV", "PY", "RV", "RV"}  # PV=Payment Voucher, PY=Payment, RV=Receipt Voucher
    for e in entries:
        if e.doc_type not in normal_types and e.amount > 5000:
            if any(e.gl_account.startswith(acct) for acct in suspicious_accounts):
                findings.append(RawFinding(
                    type="GL — Unusual Document Type",
                    entity=e.account_name,
                    entity_id=e.doc_number,
                    issue=f"Unusual doc type '{e.doc_type}' on expense account {e.gl_account} — ${e.amount:,.2f}",
                    evidence=[
                        f"F0911 doc_type = {e.doc_type} (expected PV/PY/RV for expenses)",
                        f"Account: {e.gl_account} = ${e.amount:,.2f}",
                        f"Doc number: {e.doc_number}",
                        f"Period: {e.period}",
                    ],
                    raw_impact=e.amount,
                    jde_sources=["F0911 (General Ledger)"],
                ))

    return findings
