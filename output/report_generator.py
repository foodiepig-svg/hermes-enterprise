"""PDF report generator for Hermes Enterprise Intelligence Engine."""

import os
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ─── Colour palette ───────────────────────────────────────────────────────────

COLOUR_BG = colors.HexColor("#0a0e1a")
COLOUR_SURFACE = colors.HexColor("#111827")
COLOUR_BORDER = colors.HexColor("#374151")
COLOUR_TEXT = colors.HexColor("#f9fafb")
COLOUR_MUTED = colors.HexColor("#9ca3af")
COLOUR_ACCENT = colors.HexColor("#3b82f6")
COLOUR_HIGH = colors.HexColor("#ef4444")
COLOUR_MEDIUM = colors.HexColor("#f59e0b")
COLOUR_LOW = colors.HexColor("#10b981")
COLOUR_CRITICAL = colors.HexColor("#991b1b")
COLOUR_WHITE = colors.white


# ─── Styles ───────────────────────────────────────────────────────────────────

def _make_styles():
    base = getSampleStyleSheet()

    styles = {}

    styles["title"] = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=COLOUR_TEXT,
        spaceAfter=4,
        leading=26,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="Helvetica",
        fontSize=10,
        textColor=COLOUR_MUTED,
        spaceAfter=2,
    )
    styles["section_header"] = ParagraphStyle(
        "section_header",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=COLOUR_ACCENT,
        spaceBefore=16,
        spaceAfter=8,
        leading=16,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9,
        textColor=COLOUR_TEXT,
        leading=13,
        spaceAfter=4,
    )
    styles["body_muted"] = ParagraphStyle(
        "body_muted",
        fontName="Helvetica",
        fontSize=9,
        textColor=COLOUR_MUTED,
        leading=13,
        spaceAfter=4,
    )
    styles["kpi_label"] = ParagraphStyle(
        "kpi_label",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLOUR_MUTED,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    styles["kpi_value"] = ParagraphStyle(
        "kpi_value",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=COLOUR_TEXT,
        alignment=TA_CENTER,
        leading=24,
    )
    styles["table_header"] = ParagraphStyle(
        "table_header",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=COLOUR_MUTED,
        leading=10,
    )
    styles["table_cell"] = ParagraphStyle(
        "table_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLOUR_TEXT,
        leading=10,
    )
    styles["table_cell_muted"] = ParagraphStyle(
        "table_cell_muted",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLOUR_MUTED,
        leading=10,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=7,
        textColor=COLOUR_MUTED,
        alignment=TA_CENTER,
    )

    return styles


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _urgency_color(urgency: str) -> colors.Color:
    u = urgency.lower()
    if u == "critical":
        return COLOUR_CRITICAL
    if u == "high":
        return COLOUR_HIGH
    if u == "medium":
        return COLOUR_MEDIUM
    return COLOUR_LOW


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return "—"
    text = str(text).replace("\n", " ").strip()
    if len(text) > max_chars:
        return text[:max_chars-3] + "..."
    return text


def _parse_impact(impact_str: str) -> float:
    """Parse a financial impact string like '$42K' or '$1.2M' into a float."""
    if not impact_str:
        return 0.0
    s = str(impact_str).replace("$", "").replace(",", "").replace(",", "").strip()
    mult = 1.0
    if s.endswith("K"):
        mult = 1_000
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1_000_000
        s = s[:-1]
    elif s.endswith(" annual upside at risk"):
        s = s.replace(" annual upside at risk", "")
    elif s.endswith(" potential duplicate payment"):
        s = s.replace(" potential duplicate payment", "")
    try:
        return float(s) * mult
    except (ValueError, TypeError):
        return 0.0


# ─── Report sections ──────────────────────────────────────────────────────────

def _build_header(story, styles):
    today = date.today().strftime("%d %B %Y")
    story.append(Paragraph("Hermes Enterprise", styles["title"]))
    story.append(Paragraph("Intelligence Report — CFO Summary", styles["subtitle"]))
    story.append(Paragraph(f"Generated {today}", styles["body_muted"]))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOUR_BORDER, spaceAfter=10))


def _build_kpi_table(story, summary: dict, styles):
    total = summary.get("total_findings", 0)
    by_urgency = summary.get("by_urgency", {})
    total_exposure = summary.get("total_exposure_usd", 0)

    critical = by_urgency.get("critical", 0)
    high = by_urgency.get("high", 0)
    medium = by_urgency.get("medium", 0)
    low = by_urgency.get("low", 0)

    if total_exposure >= 1_000_000:
        exp_str = f"${total_exposure/1_000_000:.1f}M"
    elif total_exposure >= 1_000:
        exp_str = f"${total_exposure/1_000:.0f}K"
    else:
        exp_str = f"${total_exposure:,.0f}"

    kpi_data = [
        [
            Paragraph("<b>Total Findings</b>", styles["kpi_label"]),
            Paragraph("<b>Critical</b>", styles["kpi_label"]),
            Paragraph("<b>High</b>", styles["kpi_label"]),
            Paragraph("<b>Medium</b>", styles["kpi_label"]),
            Paragraph("<b>Low</b>", styles["kpi_label"]),
            Paragraph("<b>Total Exposure</b>", styles["kpi_label"]),
        ],
        [
            Paragraph(str(total), styles["kpi_value"]),
            Paragraph(str(critical), ParagraphStyle("v_h", fontName="Helvetica-Bold", fontSize=20, textColor=COLOUR_CRITICAL, alignment=TA_CENTER, leading=24)),
            Paragraph(str(high), ParagraphStyle("v_h", fontName="Helvetica-Bold", fontSize=20, textColor=COLOUR_HIGH, alignment=TA_CENTER, leading=24)),
            Paragraph(str(medium), ParagraphStyle("v_h", fontName="Helvetica-Bold", fontSize=20, textColor=COLOUR_MEDIUM, alignment=TA_CENTER, leading=24)),
            Paragraph(str(low), ParagraphStyle("v_h", fontName="Helvetica-Bold", fontSize=20, textColor=COLOUR_LOW, alignment=TA_CENTER, leading=24)),
            Paragraph(exp_str, ParagraphStyle("v_h", fontName="Helvetica-Bold", fontSize=20, textColor=COLOUR_TEXT, alignment=TA_CENTER, leading=24)),
        ],
    ]

    kpi_table = Table(kpi_data, colWidths=[2.2*cm]*6)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOUR_SURFACE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOUR_SURFACE]),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOUR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(kpi_table)
    story.append(Spacer(1, 12))


def _build_findings_table(story, findings: list, styles):
    story.append(Paragraph("Findings Detail", styles["section_header"]))

    header = [
        Paragraph("TYPE", styles["table_header"]),
        Paragraph("ENTITY", styles["table_header"]),
        Paragraph("ISSUE", styles["table_header"]),
        Paragraph("IMPACT", styles["table_header"]),
        Paragraph("CONFIDENCE", styles["table_header"]),
        Paragraph("URGENCY", styles["table_header"]),
        Paragraph("RECOMMENDATION", styles["table_header"]),
    ]

    rows = [header]
    for f in findings:
        urg = f.get("urgency", "Medium")
        rows.append([
            Paragraph(_truncate(f.get("type", "—"), 20), styles["table_cell"]),
            Paragraph(_truncate(f.get("entity", "—"), 22), styles["table_cell"]),
            Paragraph(_truncate(f.get("issue", "—"), 35), styles["table_cell"]),
            Paragraph(f.get("financial_impact", "—"), styles["table_cell"]),
            Paragraph(f.get("confidence", "—"), styles["table_cell"]),
            Paragraph(urg, ParagraphStyle(
                "urg", fontName="Helvetica-Bold", fontSize=8,
                textColor=_urgency_color(urg), leading=10
            )),
            Paragraph(_truncate(f.get("recommendation", "—"), 50), styles["table_cell_muted"]),
        ])

    col_widths = [2.5*cm, 3.0*cm, 4.0*cm, 2.0*cm, 1.8*cm, 1.8*cm, 5.5*cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOUR_SURFACE),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOUR_MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, COLOUR_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOUR_SURFACE, colors.HexColor("#0f1520")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COLOUR_ACCENT),
    ]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)


# ─── Main generator ───────────────────────────────────────────────────────────

def generate_pdf_report(findings: list, summary: dict, output_path: str) -> str:
    """
    Generate a PDF intelligence report.

    Args:
        findings: List of enriched finding dicts.
        summary:  Summary dict with total_findings, by_urgency, total_exposure_usd.
        output_path: Path to write the PDF file.

    Returns:
        Path to the generated PDF file.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = _make_styles()

    story = []

    # — Header
    _build_header(story, styles)

    # — KPI strip
    _build_kpi_table(story, summary, styles)

    # — Findings table
    if findings:
        _build_findings_table(story, findings, styles)
    else:
        story.append(Paragraph("No findings to report.", styles["body_muted"]))

    # — Footer note
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COLOUR_BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This report was generated by Hermes Enterprise Intelligence Engine. "
        "Findings are based on deterministic detection rules applied to JDE ERP data. "
        "Financial impact figures are estimates. All findings should be verified against source documents "
        "before taking action.",
        styles["footer"]
    ))

    doc.build(story)
    return output_path
