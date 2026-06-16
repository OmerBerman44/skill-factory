"""
Monthly Close Assistant — AR reminders: eligibility scan (deterministic, READ-ONLY)

PATTERN 2 + gated-write split. This script decides WHO is eligible for a reminder/escalation
and re-checks each invoice's CURRENT balance. It does NOT send anything and does NOT mutate
QuickBooks or the ledger — sending (Gmail) and ledger updates are the agent's job, gated by the
approved reminder policy + kill switch (see SKILL.md § Critical rules — outbound communication).

Why a script: "who is due, at what stage, is it still unpaid" must be deterministic and must
re-read live balances so we never chase a paid invoice. The agent then drafts + sends + logs.

Usage:
  python3 reminders_due.py <company_id> <ledger_sheet_id>

Env:
  QUICKBOOKS_ACCESS_TOKEN     (required) — read scope.
  GOOGLESHEETS_ACCESS_TOKEN   (required) — read the reminder ledger.
  QUICKBOOKS_API_BASE         (optional) — defaults to production.
  QUICKBOOKS_MINOR_VERSION    (optional) — default 75.
  REMINDER_FIRST_TRIGGER      (optional) — "on_due" | "days_after:N" | "days_before:N" (default on_due)
  REMINDER_ESCALATION_DAYS    (optional) — days after last reminder before a follow-up (default 7)
  REMINDER_MAX_ATTEMPTS       (optional) — max reminders per invoice (default 3)

Ledger tab: `ar_reminders` with columns:
  invoice_id, customer, billing_email, doc_number, invoice_date, due_date, amount,
  stage(none|first|escalation), attempts, first_reminder_at, last_reminder_at,
  status(open|paid|disputed|stopped), opted_out(TRUE|FALSE), notes

Output (stdout JSON): the single source of truth for what the agent may send:
  {
    "policy":  {...},
    "to_send": [ {invoice_id, customer, billing_email, doc_number, due_date, amount,
                  days_overdue, stage, prior_attempts} ],
    "skipped": [ {invoice_id, reason} ]
  }

QuickBooks/Sheets specifics are marked `# VERIFY` — confirm against live APIs before production.
"""

import os
import sys
import json
import datetime as dt

import requests

# ── ARGS / ENV ──────────────────────────────────────────────────────────────
QB_TOKEN = os.environ.get("QUICKBOOKS_ACCESS_TOKEN", "")
GS_TOKEN = os.environ.get("GOOGLESHEETS_ACCESS_TOKEN", "")
if not QB_TOKEN or not GS_TOKEN:
    print("ERROR: QUICKBOOKS_ACCESS_TOKEN and GOOGLESHEETS_ACCESS_TOKEN are both required.",
          file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 3:
    print("ERROR: usage: reminders_due.py <company_id> <ledger_sheet_id>", file=sys.stderr)
    sys.exit(1)

COMPANY_ID = sys.argv[1]
LEDGER_SHEET_ID = sys.argv[2]

API_BASE = os.environ.get("QUICKBOOKS_API_BASE", "https://quickbooks.api.intuit.com")
MINOR_VERSION = os.environ.get("QUICKBOOKS_MINOR_VERSION", "75")
QB_HEADERS = {"Authorization": f"Bearer {QB_TOKEN}", "Accept": "application/json"}
GS_HEADERS = {"Authorization": f"Bearer {GS_TOKEN}"}
TODAY = dt.date.today()

FIRST_TRIGGER = os.environ.get("REMINDER_FIRST_TRIGGER", "on_due")
ESCALATION_DAYS = int(os.environ.get("REMINDER_ESCALATION_DAYS", "7"))
MAX_ATTEMPTS = int(os.environ.get("REMINDER_MAX_ATTEMPTS", "3"))
PAGE = 1000


# ── HELPERS ─────────────────────────────────────────────────────────────────
def to_date(s):
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def days_between(a, b):
    return (a - b).days if a and b else None


# ── QUICKBOOKS (read-only) ──────────────────────────────────────────────────
def qb_query_all(base_query, key):
    out, start = [], 1
    while True:
        url = f"{API_BASE}/v3/company/{COMPANY_ID}/query"
        r = requests.get(url, headers=QB_HEADERS,
                         params={"query": f"{base_query} STARTPOSITION {start} MAXRESULTS {PAGE}",
                                 "minorversion": MINOR_VERSION})
        if r.status_code != 200:
            print(f"ERROR: QuickBooks query failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        batch = r.json().get("QueryResponse", {}).get(key, [])
        out.extend(batch)
        if len(batch) < PAGE:
            return out
        start += PAGE


def get_open_invoices():
    # VERIFY: Invoice.BillEmail.Address for the recipient; Balance/DueDate/TxnDate/DocNumber.
    out = []
    for inv in qb_query_all("SELECT * FROM Invoice WHERE Balance > '0'", "Invoice"):
        due = inv.get("DueDate", inv.get("TxnDate", ""))
        out.append({
            "invoice_id":   str(inv.get("Id")),
            "customer":     (inv.get("CustomerRef") or {}).get("name", ""),
            "billing_email": (inv.get("BillEmail") or {}).get("Address", ""),
            "doc_number":   inv.get("DocNumber", ""),
            "invoice_date": inv.get("TxnDate", ""),
            "due_date":     due,
            "amount":       round(float(inv.get("Balance", 0) or 0), 2),  # CURRENT balance (re-checked)
            "days_overdue": (days_between(TODAY, to_date(due)) or 0),
        })
    return out


# ── LEDGER (read-only) ──────────────────────────────────────────────────────
def read_ledger():
    r = requests.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{LEDGER_SHEET_ID}/values/ar_reminders",
        headers=GS_HEADERS)
    if r.status_code != 200:
        return {}
    rows = r.json().get("values", [])
    if len(rows) < 1:
        return {}
    headers = [h.lower().strip() for h in rows[0]]
    idx = {h: i for i, h in enumerate(headers)}
    out = {}
    for row in rows[1:]:
        def cell(name):
            i = idx.get(name)
            return row[i] if i is not None and i < len(row) else ""
        inv_id = cell("invoice_id")
        if not inv_id:
            continue
        out[inv_id] = {
            "stage":             (cell("stage") or "none").strip().lower(),
            "attempts":          int(cell("attempts") or 0) if str(cell("attempts")).strip().isdigit() else 0,
            "last_reminder_at":  cell("last_reminder_at"),
            "status":            (cell("status") or "open").strip().lower(),
            "opted_out":         str(cell("opted_out")).strip().lower() in ("true", "yes", "1"),
        }
    return out


# ── ELIGIBILITY ─────────────────────────────────────────────────────────────
def first_reminder_due(inv):
    due = to_date(inv["due_date"])
    if not due:
        return False
    if FIRST_TRIGGER.startswith("days_after:"):
        return inv["days_overdue"] >= int(FIRST_TRIGGER.split(":")[1])
    if FIRST_TRIGGER.startswith("days_before:"):
        return TODAY >= due - dt.timedelta(days=int(FIRST_TRIGGER.split(":")[1]))
    return due <= TODAY  # on_due


def decide(inv, led):
    """Return (stage_to_send | None, skip_reason | None)."""
    if not inv["billing_email"]:
        return None, "no_billing_email"          # never guess a recipient
    if led:
        if led["status"] in ("paid", "stopped", "disputed"):
            return None, f"status_{led['status']}"
        if led["opted_out"]:
            return None, "opted_out"
        if led["attempts"] >= MAX_ATTEMPTS:
            return None, "max_attempts_reached"
        last = to_date(led["last_reminder_at"])
        stage = led["stage"]
        if stage in ("first", "escalation"):
            if last and days_between(TODAY, last) < ESCALATION_DAYS:
                return None, "waiting_for_escalation_window"
            return "escalation", None
    # no prior reminder
    if first_reminder_due(inv):
        return "first", None
    return None, "not_yet_due"


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    ledger = read_ledger()
    open_invoices = get_open_invoices()

    to_send, skipped = [], []
    for inv in open_invoices:
        led = ledger.get(inv["invoice_id"])
        stage, reason = decide(inv, led)
        if stage:
            to_send.append({
                "invoice_id":    inv["invoice_id"],
                "customer":      inv["customer"],
                "billing_email": inv["billing_email"],
                "doc_number":    inv["doc_number"],
                "due_date":      inv["due_date"],
                "amount":        inv["amount"],
                "days_overdue":  inv["days_overdue"],
                "stage":         stage,
                "prior_attempts": led["attempts"] if led else 0,
            })
        else:
            skipped.append({"invoice_id": inv["invoice_id"], "reason": reason})

    print(json.dumps({
        "policy": {
            "first_trigger": FIRST_TRIGGER,
            "escalation_days": ESCALATION_DAYS,
            "max_attempts": MAX_ATTEMPTS,
        },
        "to_send": to_send,
        "skipped": skipped,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
