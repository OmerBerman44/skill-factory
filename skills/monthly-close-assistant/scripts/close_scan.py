"""
Monthly Close Assistant — close scan (deterministic read + math)

PATTERN 2. The agent CALLS this; it never re-implements the math inline (see agent_rule.md).
This script does the read-only, deterministic part of the close: pull the period's data from
QuickBooks and compute the findings/aggregates. The agent reasons over the JSON it prints,
drives the (gated) write-back, and renders the summary.

Contract:
  - READ-ONLY. This script makes NO QuickBooks mutations, ever. Writes are the agent's job
    (consent-gated). This script only GETs.
  - Idempotent: same company + period → same output.
  - Every number the agent reports must come from this output ("never invent a number").
  - Fails loudly with a clear message if a required input is missing.

Usage:
  python3 close_scan.py <company_id> <period>
    company_id  — QuickBooks Online realmId / company id
    period      — YYYY-MM (e.g. 2026-05). Resolved to the full calendar month.

Env:
  QUICKBOOKS_ACCESS_TOKEN     (required) — fresh OAuth2 token with read scope.
  QUICKBOOKS_API_BASE         (optional) — defaults to production; set the sandbox base to test:
                                           https://sandbox-quickbooks.api.intuit.com
  QUICKBOOKS_MINOR_VERSION    (optional) — QBO API minorversion (default 75).
  MISSING_RECEIPT_THRESHOLD   (optional) — flag txns >= this amount with no attachment (default 75).
  DUPLICATE_WINDOW_DAYS       (optional) — same party+amount within N days = dup candidate (default 7).

Output: a single JSON object on stdout (the single source of truth for checklist + summary):
  {
    "period":          {label,start,end},
    "uncategorized":   [ {id,date,amount,payee,account,suggested_category,confidence} ],
    "open_ar":         [ {id,customer,doc_number,date,due_date,amount,days_overdue} ],
    "open_ap":         [ {id,vendor,doc_number,date,due_date,amount,days_overdue} ],
    "duplicates":      [ {type,party,amount,items:[{id,doc_number,date}]} ],
    "missing_receipts":[ {id,type,date,amount,party} ],
    "ar_aging":        {current,1_30,31_60,61_90,90_plus,total},
    "ap_aging":        {current,1_30,31_60,61_90,90_plus,total},
    "pnl_snapshot":    {income,expenses,net},
    "totals":          {uncategorized_count,open_ar_count,open_ap_count,
                        duplicate_clusters,missing_receipt_count,ties_out}
  }

QuickBooks-specific query strings / response shapes are marked `# VERIFY` where they should be
confirmed against a live QuickBooks Online company before production. Grep for VERIFY before ship.
"""

import os
import sys
import json
import datetime as dt
from calendar import monthrange
from collections import defaultdict

import requests

# ── ARGS / ENV ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("QUICKBOOKS_ACCESS_TOKEN", "")
if not TOKEN:
    print("ERROR: QUICKBOOKS_ACCESS_TOKEN environment variable is required.", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 3:
    print("ERROR: usage: close_scan.py <company_id> <period:YYYY-MM>", file=sys.stderr)
    sys.exit(1)

COMPANY_ID = sys.argv[1]
PERIOD_ARG = sys.argv[2]

API_BASE = os.environ.get("QUICKBOOKS_API_BASE", "https://quickbooks.api.intuit.com")
MINOR_VERSION = os.environ.get("QUICKBOOKS_MINOR_VERSION", "75")  # VERIFY: current QBO minorversion
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}
TODAY = dt.date.today()

MISSING_RECEIPT_THRESHOLD = float(os.environ.get("MISSING_RECEIPT_THRESHOLD", "75"))
DUPLICATE_WINDOW_DAYS = int(os.environ.get("DUPLICATE_WINDOW_DAYS", "7"))
PAGE = 1000  # QBO max page size

# Accounts QBO posts to when a bank-feed item hasn't been categorized yet.
# VERIFY against the company's chart of accounts; names can be localized/renamed.
UNCATEGORIZED_ACCOUNTS = {"Uncategorized Expense", "Uncategorized Income", "Uncategorized Asset"}


# ── PERIOD ──────────────────────────────────────────────────────────────────
def resolve_period(period_arg):
    try:
        y, m = (int(x) for x in period_arg.split("-"))
        start = dt.date(y, m, 1)
        end = dt.date(y, m, monthrange(y, m)[1])
    except Exception:
        print(f"ERROR: bad period '{period_arg}', expected YYYY-MM.", file=sys.stderr)
        sys.exit(1)
    return {"label": start.strftime("%B %Y"), "start": start.isoformat(), "end": end.isoformat()}


def prev_period(period):
    """The calendar month before the given period (for month-over-month comparison)."""
    s = dt.date.fromisoformat(period["start"])
    py, pm = (s.year, s.month - 1) if s.month > 1 else (s.year - 1, 12)
    start = dt.date(py, pm, 1)
    end = dt.date(py, pm, monthrange(py, pm)[1])
    return {"label": start.strftime("%B %Y"), "start": start.isoformat(), "end": end.isoformat()}


# ── QUICKBOOKS API (read-only) ───────────────────────────────────────────────
def qb_query_page(query):
    """Run one QBO query against the /query endpoint. Read-only GET."""
    url = f"{API_BASE}/v3/company/{COMPANY_ID}/query"
    r = requests.get(url, headers=HEADERS,
                     params={"query": query, "minorversion": MINOR_VERSION})
    if r.status_code != 200:
        print(f"ERROR: QuickBooks query failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return r.json().get("QueryResponse", {})


def qb_query_all(base_query, entity_key):
    """Page through a query (STARTPOSITION/MAXRESULTS) until exhausted. base_query must NOT
    include pagination clauses. VERIFY: QBO pagination is 1-indexed via STARTPOSITION."""
    out, start = [], 1
    while True:
        resp = qb_query_page(f"{base_query} STARTPOSITION {start} MAXRESULTS {PAGE}")
        batch = resp.get(entity_key, [])
        out.extend(batch)
        if len(batch) < PAGE:
            return out
        start += PAGE


def qb_pnl(start, end):
    """Profit & Loss report via the Reports endpoint. Read-only GET."""
    url = f"{API_BASE}/v3/company/{COMPANY_ID}/reports/ProfitAndLoss"
    r = requests.get(url, headers=HEADERS,
                     params={"start_date": start, "end_date": end, "minorversion": MINOR_VERSION})
    if r.status_code != 200:
        print(f"ERROR: P&L report failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


# ── AGING ───────────────────────────────────────────────────────────────────
def aging_bucket(days):
    if days <= 0:   return "current"
    if days <= 30:  return "1_30"
    if days <= 60:  return "31_60"
    if days <= 90:  return "61_90"
    return "90_plus"


def build_aging(open_items):
    buckets = defaultdict(float)
    for it in open_items:
        buckets[aging_bucket(it["days_overdue"])] += it["amount"]
    return {
        "current": round(buckets["current"], 2),
        "1_30":    round(buckets["1_30"], 2),
        "31_60":   round(buckets["31_60"], 2),
        "61_90":   round(buckets["61_90"], 2),
        "90_plus": round(buckets["90_plus"], 2),
        "total":   round(sum(buckets.values()), 2),
    }


def days_overdue(due_date_iso):
    try:
        due = dt.date.fromisoformat(due_date_iso)
    except Exception:
        return 0
    return (TODAY - due).days


def _days_between(a_iso, b_iso):
    try:
        return abs((dt.date.fromisoformat(a_iso) - dt.date.fromisoformat(b_iso)).days)
    except Exception:
        return 9999


# ── COLLECTORS (all read-only) ───────────────────────────────────────────────
def get_open_ar():
    # VERIFY: Invoice entity fields (Balance, DueDate, TxnDate, DocNumber, CustomerRef).
    out = []
    for inv in qb_query_all("SELECT * FROM Invoice WHERE Balance > '0'", "Invoice"):
        due = inv.get("DueDate", inv.get("TxnDate", ""))
        out.append({
            "id":           inv.get("Id"),
            "customer":     (inv.get("CustomerRef") or {}).get("name", ""),
            "doc_number":   inv.get("DocNumber", ""),
            "date":         inv.get("TxnDate", ""),
            "due_date":     due,
            "amount":       round(float(inv.get("Balance", 0) or 0), 2),
            "days_overdue": days_overdue(due),
        })
    return out


def get_open_ap():
    # VERIFY: Bill entity fields (Balance, DueDate, TxnDate, DocNumber, VendorRef).
    out = []
    for bill in qb_query_all("SELECT * FROM Bill WHERE Balance > '0'", "Bill"):
        due = bill.get("DueDate", bill.get("TxnDate", ""))
        out.append({
            "id":           bill.get("Id"),
            "vendor":       (bill.get("VendorRef") or {}).get("name", ""),
            "doc_number":   bill.get("DocNumber", ""),
            "date":         bill.get("TxnDate", ""),
            "due_date":     due,
            "amount":       round(float(bill.get("Balance", 0) or 0), 2),
            "days_overdue": days_overdue(due),
        })
    return out


def get_period_purchases(start, end):
    # VERIFY: Purchase entity covers cash/card/check expenses; bank-feed "For Review" items are
    # NOT Purchase objects and won't appear here — uncategorized detection here is best-effort.
    return qb_query_all(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}'", "Purchase")


def get_period_bills(start, end):
    return qb_query_all(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start}' AND TxnDate <= '{end}'", "Bill")


def get_uncategorized(purchases):
    out = []
    for p in purchases:
        for line in p.get("Line", []):
            acct = (((line.get("AccountBasedExpenseLineDetail") or {}).get("AccountRef")) or {}).get("name", "")
            if acct in UNCATEGORIZED_ACCOUNTS:
                out.append({
                    "id":         p.get("Id"),
                    "date":       p.get("TxnDate", ""),
                    "amount":     round(float(p.get("TotalAmt", 0) or 0), 2),
                    "payee":      (p.get("EntityRef") or {}).get("name", ""),
                    "account":    acct,
                    "suggested_category": None,   # the agent proposes; the script never guesses
                    "confidence": None,
                })
                break
    return out


def find_duplicates(bills, invoices):
    """Cluster same-party + same-amount docs whose dates fall within DUPLICATE_WINDOW_DAYS.
    Surfaces CANDIDATES only — never merges. The agent (with the user) decides."""
    clusters = []

    def cluster(items, party_key, type_label):
        groups = defaultdict(list)
        for it in items:
            party = (it.get(party_key) or {}).get("name", "")
            amount = round(float(it.get("TotalAmt", 0) or 0), 2)
            groups[(party, amount)].append(it)
        for (party, amount), grp in groups.items():
            if len(grp) < 2:
                continue
            grp.sort(key=lambda x: x.get("TxnDate", ""))
            # any pair within the window → flag the whole group as candidates
            near = any(_days_between(grp[i]["TxnDate"], grp[j]["TxnDate"]) <= DUPLICATE_WINDOW_DAYS
                       for i in range(len(grp)) for j in range(i + 1, len(grp)))
            if near:
                clusters.append({
                    "type":   type_label,
                    "party":  party,
                    "amount": amount,
                    "items":  [{"id": g.get("Id"), "doc_number": g.get("DocNumber", ""),
                                "date": g.get("TxnDate", "")} for g in grp],
                })

    cluster(bills, "VendorRef", "Bill")
    cluster(invoices, "CustomerRef", "Invoice")
    return clusters


def get_referenced_txn_keys():
    """Set of (entityType, id) that have an attachment, from the Attachable entity.
    VERIFY: Attachable.AttachableRef[].EntityRef {type, value}."""
    keys = set()
    for att in qb_query_all("SELECT * FROM Attachable", "Attachable"):
        for ref in att.get("AttachableRef", []):
            ent = ref.get("EntityRef") or {}
            if ent.get("value"):
                keys.add((ent.get("type"), str(ent.get("value"))))
    return keys


def find_missing_receipts(purchases, bills, attached_keys):
    """Period txns at/above the threshold with no linked attachment."""
    out = []
    for p in purchases:
        amt = round(float(p.get("TotalAmt", 0) or 0), 2)
        if amt >= MISSING_RECEIPT_THRESHOLD and ("Purchase", str(p.get("Id"))) not in attached_keys:
            out.append({"id": p.get("Id"), "type": "Purchase", "date": p.get("TxnDate", ""),
                        "amount": amt, "party": (p.get("EntityRef") or {}).get("name", "")})
    for b in bills:
        amt = round(float(b.get("TotalAmt", 0) or 0), 2)
        if amt >= MISSING_RECEIPT_THRESHOLD and ("Bill", str(b.get("Id"))) not in attached_keys:
            out.append({"id": b.get("Id"), "type": "Bill", "date": b.get("TxnDate", ""),
                        "amount": amt, "party": (b.get("VendorRef") or {}).get("name", "")})
    return out


def parse_pnl(report):
    """Pull income / expenses / net from the P&L report. Prefer the report's own NetIncome
    summary; fall back to income - expenses. VERIFY: QBO report Rows/Summary shape + group names."""
    found = {}

    def walk(rows):
        row_list = rows.get("Row", []) if isinstance(rows, dict) else rows
        for row in row_list:
            grp = row.get("group")
            summary = row.get("Summary", {})
            cols = summary.get("ColData", []) if summary else []
            if grp and cols:
                try:
                    found[grp] = float(cols[-1].get("value", 0) or 0)
                except Exception:
                    pass
            if "Rows" in row:
                walk(row["Rows"])

    try:
        walk(report.get("Rows", {}))
    except Exception:
        pass

    income = found.get("Income", 0.0)
    expenses = found.get("Expenses", 0.0)
    net = found.get("NetIncome", income - expenses)
    return {"income": round(income, 2), "expenses": round(expenses, 2), "net": round(net, 2)}


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    period = resolve_period(PERIOD_ARG)
    start, end = period["start"], period["end"]

    open_ar = get_open_ar()
    open_ap = get_open_ap()

    purchases = get_period_purchases(start, end)
    period_bills = get_period_bills(start, end)
    period_invoices = qb_query_all(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start}' AND TxnDate <= '{end}'", "Invoice")

    uncategorized = get_uncategorized(purchases)
    duplicates = find_duplicates(period_bills, period_invoices)
    missing_receipts = find_missing_receipts(purchases, period_bills, get_referenced_txn_keys())
    pnl = parse_pnl(qb_pnl(start, end))

    # Prior-period P&L for month-over-month comparison in the summary.
    prev = prev_period(period)
    pnl_prev = parse_pnl(qb_pnl(prev["start"], prev["end"]))
    pnl_delta = {k: round(pnl[k] - pnl_prev[k], 2) for k in ("income", "expenses", "net")}

    ar_aging = build_aging(open_ar)
    ap_aging = build_aging(open_ap)

    # Tie-out: aging buckets must sum to item totals.
    ar_sum = round(sum(i["amount"] for i in open_ar), 2)
    ap_sum = round(sum(i["amount"] for i in open_ap), 2)
    ties_out = (abs(ar_sum - ar_aging["total"]) < 0.01 and
                abs(ap_sum - ap_aging["total"]) < 0.01)

    result = {
        "period":           period,
        "uncategorized":    uncategorized,
        "open_ar":          open_ar,
        "open_ap":          open_ap,
        "duplicates":       duplicates,
        "missing_receipts": missing_receipts,
        "ar_aging":         ar_aging,
        "ap_aging":         ap_aging,
        "pnl_snapshot":     pnl,
        "pnl_prev":         pnl_prev,
        "pnl_delta":        pnl_delta,
        "prev_period":      prev,
        "totals": {
            "uncategorized_count":  len(uncategorized),
            "open_ar_count":        len(open_ar),
            "open_ap_count":        len(open_ap),
            "duplicate_clusters":   len(duplicates),
            "missing_receipt_count": len(missing_receipts),
            "ties_out":             ties_out,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
