"""
Monthly Close Assistant — accountant summary PDF (deterministic renderer)

PATTERN 2. Renders a 2-page, accountant-grade summary from the close-scan JSON. It does NOT
re-query QuickBooks — it consumes the SAME JSON that close_scan.py produced, so every number on
the PDF ties to the scan (single source of truth). The agent runs close_scan.py, saves the JSON,
then calls this; the agent delivers the PDF in chat and emails it to the accountant.

Page 1 (at a glance): branded header + "prepared for/by" + executive summary + KPI cards +
  color-coded AR-aging bar chart + close-readiness split (blockers vs. informational).
Page 2 (the detail): overdue/open AR table, duplicate clusters, missing receipts, recommended
  actions. Empty sections collapse to a one-line note instead of blank tables.

Usage:
  python3 accountant_summary.py <scan_json_path> <output_pdf_path> [company_name] [accountant_email]

Reads nothing from the network. Requires matplotlib (same runtime dep as other renderers).
"""

import os
import sys
import json
import datetime as dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.backends.backend_pdf import PdfPages

# ── ARGS ────────────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("ERROR: usage: accountant_summary.py <scan_json> <out.pdf> [company] [accountant_email]",
          file=sys.stderr)
    sys.exit(1)

SCAN_PATH = sys.argv[1]
OUTPUT_PATH = sys.argv[2]
COMPANY = sys.argv[3] if len(sys.argv) > 3 else ""
ACCOUNTANT = sys.argv[4] if len(sys.argv) > 4 else ""

if not os.path.exists(SCAN_PATH):
    print(f"ERROR: scan json not found: {SCAN_PATH}", file=sys.stderr)
    sys.exit(1)

with open(SCAN_PATH) as f:
    scan = json.load(f)

GENERATED = dt.date.today().strftime("%b %d, %Y")
CUR = os.environ.get("CURRENCY_SYMBOL", "$")

# ── PALETTE ─────────────────────────────────────────────────────────────────
INK = "#0F172A"; SUB = "#475569"; MUTED = "#94A3B8"; LINE = "#E2E8F0"
S0 = "#FFFFFF"; S50 = "#F8FAFC"; S100 = "#F1F5F9"
ACCENT = "#F97316"; BLUE = "#3B82F6"; GREEN = "#16A34A"
RED = "#DC2626"; AMBER = "#F59E0B"; AMBER2 = "#FBBF24"

AGING_COLORS = {"current": BLUE, "1_30": AMBER2, "31_60": AMBER,
                "61_90": "#FB7185", "90_plus": RED}
AGING_LABELS = [("current", "Current"), ("1_30", "1–30 days"), ("31_60", "31–60 days"),
                ("61_90", "61–90 days"), ("90_plus", "90+ days")]


# ── DATA ────────────────────────────────────────────────────────────────────
def money(v):
    try:
        return f"{CUR}{float(v):,.2f}"
    except Exception:
        return str(v)


def money0(v):
    try:
        return f"{CUR}{float(v):,.0f}"
    except Exception:
        return str(v)


period   = scan.get("period", {})
totals   = scan.get("totals", {})
pnl      = scan.get("pnl_snapshot", {})
delta    = scan.get("pnl_delta", {})
ar       = scan.get("open_ar", [])
ar_aging = scan.get("ar_aging", {})
ap_aging = scan.get("ap_aging", {})
dups     = scan.get("duplicates", [])
missing  = scan.get("missing_receipts", [])

income = float(pnl.get("income", 0) or 0)
expenses = float(pnl.get("expenses", 0) or 0)
net = float(pnl.get("net", 0) or 0)
ar_total = float(ar_aging.get("total", 0) or 0)
overdue = sorted([i for i in ar if (i.get("days_overdue") or 0) > 0],
                 key=lambda x: -(x.get("days_overdue") or 0))
overdue_amt = round(sum(float(i.get("amount", 0) or 0) for i in overdue), 2)
b90 = float(ar_aging.get("90_plus", 0) or 0)
items_to_fix = (totals.get("uncategorized_count", 0) + totals.get("duplicate_clusters", 0)
                + totals.get("missing_receipt_count", 0))


def exec_summary():
    bits = [f"{period.get('label','')} net income {money0(net)}"]
    if expenses == 0:
        bits[0] += " (no expenses recorded)"
    if ar_total:
        s = f"{money0(ar_total)} AR outstanding across {totals.get('open_ar_count', 0)} invoice(s)"
        if overdue:
            s += f"; {money0(overdue_amt)} overdue"
            if b90:
                s += f", {money0(b90)} of it 90+ days — collection risk"
        bits.append(s)
    fixes = []
    if totals.get("uncategorized_count"): fixes.append(f"{totals['uncategorized_count']} to categorize")
    if totals.get("duplicate_clusters"):  fixes.append(f"{totals['duplicate_clusters']} duplicate(s)")
    if totals.get("missing_receipt_count"): fixes.append(f"{totals['missing_receipt_count']} missing receipt(s)")
    bits.append(("Blockers: " + ", ".join(fixes)) if fixes else "No blockers — books look ready to close.")
    return ".  ".join(bits) + "."


# ── DRAW PRIMITIVES (single full-page axes, data coords 0..1) ────────────────
def new_page():
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(S0)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    return fig, ax


L, Rt = 0.07, 0.93  # left / right margins


def header(ax, page_title):
    ax.add_patch(Rectangle((0, 0.945), 1, 0.055, color=INK, zorder=1))
    ax.text(L, 0.967, "Monthly Close Summary", color=S0, fontsize=18, fontweight="bold",
            va="center", zorder=2)
    sub = f"{COMPANY + '  ·  ' if COMPANY else ''}{period.get('label','')}  ·  {period.get('start','')} → {period.get('end','')}"
    ax.text(L, 0.952, sub, color="#CBD5E1", fontsize=8.5, va="center", zorder=2)
    prep = f"Prepared for {ACCOUNTANT}  ·  " if ACCOUNTANT else ""
    ax.text(Rt, 0.967, page_title, color=S0, fontsize=9, ha="right", va="center", zorder=2)
    ax.text(Rt, 0.952, f"{prep}by Monthly Close Assistant", color="#CBD5E1", fontsize=7.5,
            ha="right", va="center", zorder=2)


def footer(ax, page_no, page_total):
    ax.text(L, 0.03, f"Generated {GENERATED}  ·  numbers sourced from the close scan",
            color=MUTED, fontsize=7.5)
    ax.text(Rt, 0.03, f"Page {page_no} of {page_total}", color=MUTED, fontsize=7.5, ha="right")


def section(ax, y, label):
    ax.text(L, y, label.upper(), color=ACCENT, fontsize=10.5, fontweight="bold")
    ax.plot([L, Rt], [y - 0.008, y - 0.008], color=LINE, lw=1)
    return y - 0.028


def kpi_card(ax, x, y, w, h, label, value, sub, accent=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                facecolor=S100, edgecolor=LINE, lw=1, zorder=1))
    ax.text(x + 0.012, y + h - 0.018, label, color=SUB, fontsize=8, fontweight="bold", va="top")
    ax.text(x + 0.012, y + h * 0.40, value, color=accent, fontsize=15, fontweight="bold", va="center")
    ax.text(x + 0.012, y + 0.016, sub, color=MUTED, fontsize=7.5, va="center")


def table(ax, y, cols, rows, widths, aligns, row_h=0.026, max_rows=16, empty_msg=None):
    """cols: header labels; rows: list of tuples; widths/aligns per column (fractions of L..Rt)."""
    span = Rt - L
    xs = [L]
    for wfrac in widths[:-1]:
        xs.append(xs[-1] + wfrac * span)
    # header
    ax.add_patch(Rectangle((L, y - row_h + 0.004), span, row_h, color=INK, zorder=1))
    for c, x, al in zip(cols, xs, aligns):
        tx = x + (0.006 if al == "left" else (widths[cols.index(c)] * span - 0.006))
        ha = "left" if al == "left" else "right"
        ax.text(tx, y - row_h / 2 + 0.004, c, color=S0, fontsize=8, fontweight="bold",
                ha=ha, va="center", zorder=2)
    y -= row_h
    if not rows:
        ax.text(L + 0.006, y - row_h / 2, empty_msg or "None.", color=MUTED, fontsize=8.5,
                style="italic", va="center")
        return y - row_h
    shown = rows[:max_rows]
    for i, row in enumerate(shown):
        if i % 2 == 1:
            ax.add_patch(Rectangle((L, y - row_h + 0.004), span, row_h, color=S50, zorder=0))
        for val, x, al, wfrac in zip(row, xs, aligns, widths):
            tx = x + (0.006 if al == "left" else (wfrac * span - 0.006))
            ha = "left" if al == "left" else "right"
            color = val[1] if isinstance(val, tuple) else INK
            text = val[0] if isinstance(val, tuple) else val
            ax.text(tx, y - row_h / 2 + 0.004, str(text), color=color, fontsize=8.2,
                    ha=ha, va="center")
        y -= row_h
    if len(rows) > max_rows:
        ax.text(L + 0.006, y - row_h / 2, f"… and {len(rows) - max_rows} more", color=MUTED,
                fontsize=7.5, style="italic", va="center")
        y -= row_h
    return y


# ── PAGE 1 ──────────────────────────────────────────────────────────────────
def page1(pdf):
    fig, ax = new_page()
    header(ax, "At a glance")

    # Executive summary panel
    y = 0.905
    ax.add_patch(FancyBboxPatch((L, y - 0.052), Rt - L, 0.062,
                 boxstyle="round,pad=0.004,rounding_size=0.01",
                 facecolor=S50, edgecolor=LINE, lw=1))
    ax.text(L + 0.012, y - 0.004, "EXECUTIVE SUMMARY", color=SUB, fontsize=8, fontweight="bold", va="top")
    ax.text(L + 0.012, y - 0.022, exec_summary(), color=INK, fontsize=9, va="top",
            wrap=True, ha="left")

    # KPI cards
    y = 0.815
    cards_w, gap = (Rt - L - 3 * 0.015) / 4, 0.015
    h = 0.075
    net_sub = f"Income {money0(income)} · Exp {money0(expenses)}"
    if delta:
        d = delta.get("net", 0)
        net_sub = f"MoM {'+' if d >= 0 else ''}{money0(d)} · Exp {money0(expenses)}"
    kpi_card(ax, L + 0 * (cards_w + gap), y, cards_w, h, "NET INCOME", money0(net), net_sub,
             GREEN if net >= 0 else RED)
    kpi_card(ax, L + 1 * (cards_w + gap), y, cards_w, h, "AR OUTSTANDING", money0(ar_total),
             f"{totals.get('open_ar_count', 0)} open invoices", INK)
    kpi_card(ax, L + 2 * (cards_w + gap), y, cards_w, h, "OVERDUE AR", money0(overdue_amt),
             f"{len(overdue)} inv · {money0(b90)} 90+d", RED if overdue_amt else GREEN)
    kpi_card(ax, L + 3 * (cards_w + gap), y, cards_w, h, "ITEMS TO FIX", str(items_to_fix),
             "uncat · dup · receipts", RED if items_to_fix else GREEN)

    # AR aging bar chart
    y = section(ax, 0.715, "AR Aging")
    vals = [float(ar_aging.get(k, 0) or 0) for k, _ in AGING_LABELS]
    mx = max(vals) or 1.0
    bar_left, bar_w_max, bar_h, rh = 0.20, 0.58, 0.022, 0.034
    for i, (k, lab) in enumerate(AGING_LABELS):
        yy = y - i * rh
        v = float(ar_aging.get(k, 0) or 0)
        ax.text(L, yy, lab, color=SUB, fontsize=8.5, va="center")
        ax.add_patch(Rectangle((bar_left, yy - bar_h / 2), bar_w_max, bar_h, color=S100, zorder=1))
        if v > 0:
            ax.add_patch(Rectangle((bar_left, yy - bar_h / 2), bar_w_max * (v / mx), bar_h,
                                   color=AGING_COLORS[k], zorder=2))
        ax.text(Rt, yy, money(v), color=INK, fontsize=8.5, fontweight="bold", ha="right", va="center")
    yy = y - len(AGING_LABELS) * rh
    ax.plot([bar_left, Rt], [yy + 0.006, yy + 0.006], color=LINE, lw=1)
    ax.text(L, yy - 0.006, "Total", color=INK, fontsize=8.5, fontweight="bold", va="center")
    ax.text(Rt, yy - 0.006, money(ar_total), color=INK, fontsize=9, fontweight="bold",
            ha="right", va="center")

    # Close readiness: blockers vs informational
    y = section(ax, 0.46, "Close readiness")
    colx2 = 0.52

    def stat(x, yy, label, count, blocker):
        clr = (RED if count else GREEN) if blocker else INK
        flag = "  ⚠" if (blocker and count) else ("  ✓" if blocker else "")
        ax.text(x, yy, label, color=SUB, fontsize=9, va="center")
        ax.text(x + 0.40, yy, f"{count}{flag}", color=clr, fontsize=9, fontweight="bold",
                ha="right", va="center")

    ax.text(L, y, "Blockers", color=INK, fontsize=9, fontweight="bold")
    ax.text(colx2, y, "Informational", color=INK, fontsize=9, fontweight="bold")
    rows_b = [("Uncategorized txns", totals.get("uncategorized_count", 0)),
              ("Duplicate candidates", totals.get("duplicate_clusters", 0)),
              ("Missing receipts", totals.get("missing_receipt_count", 0))]
    rows_i = [("Open receivables (AR)", totals.get("open_ar_count", 0)),
              ("Open payables (AP)", totals.get("open_ap_count", 0)),
              ("Overdue invoices", len(overdue))]
    for i, (lab, c) in enumerate(rows_b):
        stat(L, y - 0.026 - i * 0.026, lab, c, blocker=True)
    for i, (lab, c) in enumerate(rows_i):
        stat(colx2, y - 0.026 - i * 0.026, lab, c, blocker=False)

    if not totals.get("ties_out", True):
        ax.text(L, 0.34, "⚠ AR/AP aging does not tie out to totals — verify before relying on these figures.",
                color=RED, fontsize=8.5)

    footer(ax, 1, 2)
    pdf.savefig(fig, facecolor=S0)
    plt.close(fig)


# ── PAGE 2 ──────────────────────────────────────────────────────────────────
def page2(pdf):
    fig, ax = new_page()
    header(ax, "Detail & actions")

    # Overdue / open AR table
    y = section(ax, 0.905, "Accounts receivable — open invoices")
    ar_sorted = overdue + sorted([i for i in ar if (i.get("days_overdue") or 0) <= 0],
                                 key=lambda x: -(float(x.get("amount", 0) or 0)))
    rows = []
    for i in ar_sorted:
        d = i.get("days_overdue") or 0
        days = (f"{d}d overdue", RED) if d > 0 else ("current", GREEN)
        rows.append((i.get("customer", "")[:28], i.get("doc_number", ""),
                     i.get("due_date", ""), days, money(i.get("amount", 0))))
    y = table(ax, y, ["Customer", "Invoice #", "Due", "Status", "Amount"], rows,
              widths=[0.34, 0.16, 0.16, 0.16, 0.18],
              aligns=["left", "left", "left", "left", "right"],
              max_rows=14, empty_msg="No open receivables.")

    # Duplicate candidates
    y = section(ax, y - 0.02, "Duplicate candidates")
    if not dups:
        ax.text(L + 0.006, y - 0.013, "None detected.", color=MUTED, fontsize=8.5, style="italic")
        y -= 0.03
    else:
        for cl in dups[:6]:
            its = cl.get("items", [])
            line = (f"{cl.get('type','')}: {cl.get('party','')} — {money(cl.get('amount',0))}  "
                    f"({len(its)}×: " + ", ".join(f"#{x.get('doc_number','?')} {x.get('date','')}" for x in its) + ")")
            ax.text(L + 0.006, y - 0.013, "•  " + line, color=INK, fontsize=8.5, va="center")
            y -= 0.026

    # Missing receipts
    y = section(ax, y - 0.02, "Missing receipts")
    if not missing:
        ax.text(L + 0.006, y - 0.013, "None — all transactions above threshold have receipts.",
                color=MUTED, fontsize=8.5, style="italic")
        y -= 0.03
    else:
        for m in missing[:8]:
            ax.text(L + 0.006, y - 0.013,
                    f"•  {m.get('type','')} {m.get('date','')} — {m.get('party','') or '(no payee)'} — {money(m.get('amount',0))}",
                    color=INK, fontsize=8.5, va="center")
            y -= 0.026

    # Recommended actions
    y = section(ax, y - 0.02, "Recommended actions")
    actions = []
    if totals.get("uncategorized_count"):
        actions.append(f"Categorize {totals['uncategorized_count']} transaction(s) — I can do this with your OK.")
    if totals.get("duplicate_clusters"):
        actions.append(f"Review {totals['duplicate_clusters']} duplicate candidate(s) in QuickBooks.")
    if totals.get("missing_receipt_count"):
        actions.append(f"Attach receipts to {totals['missing_receipt_count']} transaction(s).")
    if overdue:
        actions.append(f"Chase {len(overdue)} overdue invoice(s) ({money0(overdue_amt)}) — start reminders?")
    if not actions:
        actions.append("Books look ready to close — no action needed.")
    for a in actions:
        ax.text(L + 0.006, y - 0.013, "•  " + a, color=INK, fontsize=9, va="center")
        y -= 0.026

    footer(ax, 2, 2)
    pdf.savefig(fig, facecolor=S0)
    plt.close(fig)


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    with PdfPages(OUTPUT_PATH) as pdf:
        page1(pdf)
        page2(pdf)
    print(f"Summary PDF written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
