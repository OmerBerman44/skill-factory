# Monthly Close Assistant — agent rules

## Always check the skill before acting

For ANY close-related task:
1. Read `monthly-close-assistant/SKILL.md` first.
2. Follow the documented procedure exactly — do NOT write inline code that duplicates the scan.

## The numbers come from the script, never from you

- DO NOT compute AR/AP aging, P&L totals, or "uncategorized" detection by hand or with ad-hoc
  inline code.
- DO run `.agents/skills/monthly-close-assistant/scripts/close_scan.py <company_id> <period>` and reason over its JSON output.
- If a number is not in the scan output, do not state it. Never fabricate a figure.

## Writes are gated — no exceptions

- `close_scan.py` is **read-only**. It never mutates QuickBooks.
- Any mutation (v1: categorizing a transaction) goes through the **Confirmation protocol** in
  `reference.md`: propose the exact change → get explicit per-item/per-list consent → re-read →
  write → report.
- "Fix everything" alone is NOT consent — present the full reviewed list first, then ask.
- During a scheduled automation run there is no user to confirm → make NO writes; notify only.

## Outbound sends are gated — no exceptions

- Customer reminders/escalations: eligibility comes ONLY from `reminders_due.py`. Do not decide who
  to chase by hand. Before each send, re-verify the invoice is still unpaid — **never chase a paid
  invoice**. Send only if `reminders_enabled` is true (kill switch) and a policy is approved.
- After every successful send, immediately log it to the `ar_reminders` ledger (stage, attempts+1,
  timestamp). One send per stage per invoice.
- Recipient = the QuickBooks billing email. Missing → skip + flag. Never guess an address.
- Accountant summary: render from the close-scan JSON via `accountant_summary.py` — don't hand-build
  the PDF or restate numbers the scan didn't produce.

## Scripts exist, don't recreate them

- `close_scan.py` — pulls the period's QuickBooks data and computes findings + aggregates
  (uncategorized, open AR/AP, aging, duplicate candidates, missing receipts, P&L snapshot,
  tie-out check). Read-only. Run at the start of every close.
- `reminders_due.py` — reads open invoices (live balances) + the ledger and returns who is eligible
  for a first reminder or escalation, per the approved policy. Read-only; it never sends.
- `accountant_summary.py` — renders the accountant PDF from the saved close-scan JSON. No network.

If a figure looks wrong, re-run the scan and check `totals.ties_out` — don't patch numbers inline.
