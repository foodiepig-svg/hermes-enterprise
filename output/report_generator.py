"""
Hermes Enterprise — PDF Report Generator
Uses Playwright to render www/report.html with findings data and export as PDF.
"""

import json
import subprocess
from datetime import date
from pathlib import Path

# Project root (two levels up from output/)
PROJECT_ROOT = Path(__file__).parent.parent
REPORT_TEMPLATE = PROJECT_ROOT / "www" / "report.html"


def generate_pdf_report(findings: list[dict], output_path: str) -> str:
    """
    Render report.html with findings data via Playwright and save as PDF.

    Args:
        findings: List of enriched finding dicts
        output_path: Full path to write the PDF (e.g. /tmp/hermes_report_20260430.pdf)

    Returns:
        Path to the generated PDF file.
    """
    if not REPORT_TEMPLATE.exists():
        raise FileNotFoundError(f"Report template not found: {REPORT_TEMPLATE}")

    # Read the HTML template
    html = REPORT_TEMPLATE.read_text(encoding="utf-8")

    # Inject findings as JSON into the template (供 window.__FINDINGS__)
    findings_json = json.dumps(findings, default=str, ensure_ascii=False)
    html = html.replace(
        "const findings = window.__FINDINGS__ || [];",
        f"const findings = window.__FINDINGS__ = {findings_json};",
        1,
    )

    # Write the rendered HTML to a temp file Playwright can load
    tmp_html = f"/tmp/hermes_report_render.html"
    Path(tmp_html).write_text(html, encoding="utf-8")

    # Use Playwright via Node.js to render + export PDF
    # (Playwright Python requires browser install; Node.js is already available)
    playwright_script = f"""
const {{ chromium }} = require('/Users/WORK/.hermes/hermes-agent/node_modules/playwright');
const path = require('path');
const fs = require('fs');

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage();

  // Wait for networkidle so fonts/rendering are settled
  await page.goto('file://{tmp_html}', {{
    waitUntil: 'networkidle',
    timeout: 15000
  }});

  // Expand all card details by evaluating the page
  // (report.html shows everything in the table, no need to click)
  await page.waitForTimeout(500);

  await page.pdf({{
    path: '{output_path}',
    format: 'A4',
    printBackground: true,
    margin: {{
      top: '14mm',
      right: '14mm',
      bottom: '14mm',
      left: '14mm'
    }}
  }});

  await browser.close();
  console.log('PDF saved to: {output_path}');
}})();
"""

    result = subprocess.run(
        ["node", "-e", playwright_script],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Playwright PDF generation failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")

    return output_path


def generate(findings: list[dict]) -> str:
    """Convenience wrapper — generates to /tmp with today's date."""
    today = date.today().strftime("%Y%m%d")
    output_path = f"/tmp/hermes_report_{today}.pdf"
    return generate_pdf_report(findings, output_path)
