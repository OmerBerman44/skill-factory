"""
Monthly Close Assistant — accountant summary PDF (deterministic renderer)

PATTERN 2. Renders the accountant-ready summary as a PDF from the close scan output. It does NOT
re-query QuickBooks — it consumes the SAME JSON that close_scan.py produced, so every number on
the PDF ties to the scan (single source of truth). The agent runs close_scan.py, saves the JSON,
then calls this; the agent delivers the PDF in chat and emails it to the accountant.

Usage:
  python3 accountant_summary.py <scan_json_path> <output_pdf_path> [company_name]
    scan_json_path  — file containing close_scan.py's JSON output
    output_pdf_path — where to write the PDF (e.g. /app/close-summary.pdf)
    company_name    — optional label for the header

Reads nothing from the network. No env required.
"""

import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ── ARGS ────────────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("ERROR: usage: accountant_summary.py <scan_json_path> <output_pdf_path> [company_name]",
          file=sys.stderr)
    sys.exit(1)

SCAN_PATH = sys.argv[1]
OUTPUT_PATH = sys.argv[2]
COMPANY = sys.argv[3] if len(sys.argv) > 3 else ""

if not os.path.exists(SCAN_PATH):
    print(f"ERROR: scan json not found: {SCAN_PATH}", file=sys.stderr)
    sys.exit(1)

with open(SCAN_PATH) as f:
    scan = json.load(f)

# ── PALETTE ─────────────────────────────────────────────────────────────────
INK = "#0F172A"
SUB = "#475569"
LINE = "#CBD5E1"
RED = "#EF4444"
GREEN = "#16A34A"
ACCENT = "#F97316"


def money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)


def aging_rows(aging):
    return [
        ("Current", money(aging.get("current", 0))),
        ("1–30 days", money(aging.get("1_30", 0))),
        ("31–60 days", money(aging.get("31_60", 0))),
        ("61–90 days", money(aging.get("61_90", 0))),
        ("90+ days", money(aging.get("90_plus", 0))),
        ("Total", money(aging.get("total", 0))),
    ]


def main():
    period = scan.get("period", {})
    totals = scan.get("totals", {})
    pnl = scan.get("pnl_snapshot", {})

    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    fig.patch.set_facecolor("white")
    y = 0.95

    def text(x, yy, s, size=10, color=INK, weight="normal", ha="left"):
        fig.text(x, yy, s, fontsize=size, color=color, fontweight=weight, ha=ha)

    # Header
    text(0.06, y, "Monthly Close Summary", size=20, weight="bold")
    y -= 0.030
    subtitle = f"{COMPANY + '  ·  ' if COMPANY else ''}{period.get('label','')}  ·  {period.get('start','')} → {period.get('end','')}"
    text(0.06, y, subtitle, size=10, color=SUB)
    y -= 0.018
    fig.add_artist(plt.Line2D([0.06, 0.94], [y, y], color=LINE, lw=1))
    y -= 0.035

    # P&L snapshot
    text(0.06, y, "PROFIT & LOSS", size=11, weight="bold", color=ACCENT)
    y -= 0.025
    for label, val in [("Income", pnl.get("income", 0)),
                       ("Expenses", pnl.get("expenses", 0)),
                       ("Net", pnl.get("net", 0))]:
        clr = GREEN if (label == "Net" and float(pnl.get("net", 0) or 0) >= 0) else INK
        text(0.08, y, label, size=10, color=SUB)
        text(0.94, y, money(val), size=10, color=clr, weight="bold", ha="right")
        y -= 0.022
    y -= 0.015

    # Close readiness
    text(0.06, y, "CLOSE READINESS", size=11, weight="bold", color=ACCENT)
    y -= 0.025
    readiness = [
        ("Uncategorized transactions", totals.get("uncategorized_count", 0)),
        ("Open receivables (AR)", totals.get("open_ar_count", 0)),
        ("Open payables (AP)", totals.get("open_ap_count", 0)),
        ("Duplicate candidates", totals.get("duplicate_clusters", 0)),
        ("Missing receipts", totals.get("missing_receipt_count", 0)),
    ]
    for label, count in readiness:
        flag = "" if not count else "  ⚠" if label != "Open receivables (AR)" else ""
        clr = RED if count else GREEN
        text(0.08, y, label, size=10, color=SUB)
        text(0.94, y, f"{count}{flag}", size=10, color=clr, weight="bold", ha="right")
        y -= 0.022
    y -= 0.010
    if not totals.get("ties_out", True):
        text(0.08, y, "⚠ Aging buckets do not tie out to totals — review before relying on AR/AP.",
             size=9, color=RED)
        y -= 0.022
    y -= 0.010

    # AR / AP aging tables side by side
    def aging_block(x, title, aging):
        yy = y
        text(x, yy, title, size=11, weight="bold", color=ACCENT)
        yy -= 0.025
        for label, val in aging_rows(aging):
            weight = "bold" if label == "Total" else "normal"
            text(x + 0.02, yy, label, size=9, color=SUB, weight=weight)
            text(x + 0.40, yy, val, size=9, color=INK, weight=weight, ha="right")
            yy -= 0.020
        return yy

    end_left = aging_block(0.06, "AR AGING", scan.get("ar_aging", {}))
    end_right = aging_block(0.52, "AP AGING", scan.get("ap_aging", {}))
    y = min(end_left, end_right) - 0.020

    # Blockers / open items
    text(0.06, y, "OPEN ITEMS / BLOCKERS", size=11, weight="bold", color=ACCENT)
    y -= 0.025
    blockers = []
    if totals.get("uncategorized_count"):
        blockers.append(f"{totals['uncategorized_count']} transaction(s) need categorizing")
    if totals.get("duplicate_clusters"):
        blockers.append(f"{totals['duplicate_clusters']} possible duplicate cluster(s) to review")
    if totals.get("missing_receipt_count"):
        blockers.append(f"{totals['missing_receipt_count']} transaction(s) missing a receipt")
    overdue = [i for i in scan.get("open_ar", []) if i.get("days_overdue", 0) > 0]
    if overdue:
        blockers.append(f"{len(overdue)} overdue invoice(s) outstanding")
    if not blockers:
        blockers = ["No blockers — books look ready to close."]
    for b in blockers:
        text(0.08, y, f"•  {b}", size=10, color=INK)
        y -= 0.022

    fig.text(0.06, 0.04, "Generated by Monthly Close Assistant · numbers sourced from the close scan",
             fontsize=8, color=SUB)

    with PdfPages(OUTPUT_PATH) as pdf:
        pdf.savefig(fig, facecolor="white")
    plt.close(fig)
    print(f"Summary PDF written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
