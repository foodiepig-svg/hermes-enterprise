"""
Hermes Enterprise — Flask API Server
Handles CSV upload, runs detection, returns findings + summary.
"""

import os
import tempfile
import shutil
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from pathlib import Path

from detection.detection_engine import (
    load_leases,
    load_market_rates,
    load_ap_transactions,
    detect_lease_opportunities,
    detect_lease_expiry_risk,
    detect_ap_anomalies,
    run_detection as run_core_detection,
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

app = Flask(__name__, static_folder='www', static_url_path='')
CORS(app)

DETECTION_FILES = {
    'leases': 'data/sample_leases.csv',
    'ap': 'data/sample_ap.csv',
    'ar': 'data/sample_ar.csv',
    'gl': 'data/sample_gl.csv',
    'market_benchmarks': 'data/market_benchmarks.csv',
}


def parse_float(val):
    """Safely parse a float from a string or number."""
    if val is None or val == '':
        return 0.0
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except (ValueError, AttributeError):
        return 0.0


def run_detection(data_dir: str = None) -> list:
    """Run all detection layers on the data directory."""
    data_dir = data_dir or 'data'

    leases = load_leases(os.path.join(data_dir, 'sample_leases.csv'))
    ap_txns = load_ap_transactions(os.path.join(data_dir, 'sample_ap.csv'))
    market = load_market_rates(os.path.join(data_dir, 'market_benchmarks.csv'))
    ar_txns = load_ar_transactions(os.path.join(data_dir, 'sample_ar.csv'))
    gl_entries = load_gl_entries(os.path.join(data_dir, 'sample_gl.csv'))

    findings = []

    # Layer 1: Core detection
    findings.extend(detect_lease_opportunities(leases, market))
    findings.extend(detect_lease_expiry_risk(leases))
    findings.extend(detect_ap_anomalies(ap_txns))

    # Layer 2: AP/AR/GL
    findings.extend(detect_ar_collection_risk(ar_txns))
    findings.extend(detect_ap_double_payments(ap_txns))
    findings.extend(detect_gl_anomalies(gl_entries))

    # Layer 3: Vendor risk
    findings.extend(run_ap_extended(os.path.join(data_dir, 'sample_ap.csv')))

    # Layer 4: LLM enrichment
    findings = enrich_findings(findings)

    return findings


def make_summary(findings: list) -> dict:
    """Build executive summary from findings."""
    if not findings:
        return {
            'total_findings': 0,
            'by_urgency': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
            'by_type': {},
            'total_exposure_usd': 0,
            'top_findings': []
        }

    by_urgency = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    by_type = {}
    total_exposure = 0.0

    for f in findings:
        u = f.get('urgency', 'medium')
        if u in by_urgency:
            by_urgency[u] += 1
        t = f.get('type', 'unknown')
        by_type[t] = by_type.get(t, 0) + 1

        # Parse financial impact
        impact_str = f.get('financial_impact', '')
        if impact_str:
            val = parse_float(impact_str)
            # Handle "$XK" or "$XM" format
            if 'K' in str(impact_str).upper():
                val *= 1_000
            elif 'M' in str(impact_str).upper():
                val *= 1_000_000
            total_exposure += val

    # Sort by urgency then confidence
    urgency_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    sorted_findings = sorted(
        findings,
        key=lambda f: (urgency_order.get(f.get('urgency', 'medium'), 9),
                       -(f.get('confidence', 0) or 0))
    )

    return {
        'total_findings': len(findings),
        'by_urgency': by_urgency,
        'by_type': by_type,
        'total_exposure_usd': round(total_exposure, 2),
        'top_findings': sorted_findings[:5]
    }


# ── API Routes ──────────────────────────────────────────────────────────────

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Accept CSV file uploads and run the full detection pipeline.

    Expected form fields:
      - files: up to 5 files (leases.csv, ap.csv, ar.csv, gl.csv, market_benchmarks.csv)
      - OR fields: leases, ap, ar, gl, market_benchmarks (raw CSV text)

    Returns: JSON { findings: [...], summary: {...} }
    """
    upload_dir = None

    try:
        # Handle file uploads
        if request.files:
            upload_dir = tempfile.mkdtemp(prefix='hermes_upload_')

            # Map client filenames to expected internal names
            FILE_MAP = {
                'leases.csv': 'sample_leases.csv',
                'ap.csv': 'sample_ap.csv',
                'ar.csv': 'sample_ar.csv',
                'gl.csv': 'sample_gl.csv',
                'market_benchmarks.csv': 'market_benchmarks.csv',
            }

            for key in ['leases', 'ap', 'ar', 'gl', 'market_benchmarks']:
                if key in request.files and request.files[key]:
                    f = request.files[key]
                    fname = f.filename or f'{key}.csv'
                    mapped = FILE_MAP.get(fname, fname)
                    f.save(os.path.join(upload_dir, mapped))

            # Also handle generic 'files' field with multiple files
            if 'files' in request.files:
                for f in request.files.getlist('files'):
                    name = f.filename or 'data.csv'
                    if name.endswith('.csv'):
                        mapped = FILE_MAP.get(name, name)
                        f.save(os.path.join(upload_dir, mapped))

            # Handle raw CSV text fields
            for key in ['leases', 'ap', 'ar', 'gl', 'market_benchmarks']:
                if key in request.form and request.form[key]:
                    with open(os.path.join(upload_dir, f'{key}.csv'), 'w') as out:
                        out.write(request.form[key])

            findings = run_detection(upload_dir)
        else:
            # No files uploaded — use built-in sample data
            findings = run_detection()

        summary = make_summary(findings)

        return jsonify({
            'findings': findings,
            'summary': summary,
            'meta': {
                'finding_count': len(findings),
                'uploaded_files': os.listdir(upload_dir) if upload_dir else []
            }
        })

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

    finally:
        if upload_dir and os.path.exists(upload_dir):
            shutil.rmtree(upload_dir, ignore_errors=True)


@app.route('/api/summary', methods=['GET'])
def summary():
    """Return summary of latest run (or sample data)."""
    findings = run_detection()
    return jsonify(make_summary(findings))


@app.route('/api/findings', methods=['GET'])
def get_findings():
    """Return all findings from latest run."""
    findings = run_detection()
    return jsonify(findings)


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})


# ── Dashboard ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('www', 'index.html')


@app.route('/www/<path:path>')
def www_static(path):
    return send_from_directory('www', path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
