# Monthly Close Assistant — operating reference

The full rules for the close pipeline. `SKILL.md` routes here. v1 covers uncategorized
transactions, open AR, open AP, the checklist, and the accountant summary. Sections marked
**(planned)** are documented for direction but not yet built — don't perform them yet.

## Period resolution

- Default period = the **last full calendar month** relative to today.
- Respect the company's fiscal calendar if it differs (from `onboarding` setup).
- A "period" always resolves to an explicit inclusive date range `start..end`. Every query and
  every figure is scoped to that range. Never count outside it; never double-count.
- If the user names a period ambiguously ("close last quarter"), confirm the exact range once.

## The checks

### 1. Uncategorized transactions
- Source: `close_scan.py` → `uncategorized[]`. Each item: id, date, amount, payee/description,
  account, and (if the script could infer one) a `suggested_category` + confidence.
- Present them grouped, most material (largest amount) first.
- **Categorization suggestion funnel** (for the suggestion only — never auto-applied):
  1. The payee/account already mapped in prior categorized transactions → reuse it.
  2. LLM knowledge of the payee/vendor → a specific QuickBooks account.
  3. Genuinely unknown → leave unsuggested, mark for the user to decide.
- Applying a category is a **write** — see § Confirmation protocol. Never write without it.

### 2. Open AR (accounts receivable)
- Source: `open_ar[]` + `ar_aging{}` (buckets: current, 1–30, 31–60, 61–90, 90+).
- For each open invoice: customer, invoice #, date, due date, amount, days overdue.
- Surface: total outstanding, the aging breakdown, and the largest/most-overdue items.
- This is informational in v1 — we do not send reminders or write anything for AR.

### 3. Open AP (accounts payable)
- Source: `open_ap[]` + `ap_aging{}` (same buckets).
- For each open bill: vendor, bill #, date, due date, amount, days until/over due.
- Surface: total owed, aging breakdown, anything due in the next 7 days.
- Informational in v1 — no payments, no writes.

### 4. Duplicate invoices/bills
- Source: `close_scan.py` → `duplicates[]`. Each cluster: type (Bill/Invoice), party, amount, and
  the `items[]` that match (id, doc_number, date).
- Detection (in the script): same party + same amount with dates within `DUPLICATE_WINDOW_DAYS`
  (default 7). These are **candidates**, not confirmed duplicates.
- Present each cluster and ask the user to judge — legitimate recurring charges (e.g. two identical
  weekly deliveries) are not duplicates. **Never merge or delete** anything; surfacing only.
- If the user wants to resolve one, voiding/merging is a QuickBooks write → Confirmation protocol.
  (Note: v1's only built write is categorization; duplicate resolution is surfaced for the user to
  handle in QuickBooks unless/until a gated void action is added.)

### 5. Missing receipts
- Source: `missing_receipts[]`. Each: id, type (Purchase/Bill), date, amount, party.
- Detection (in the script): period transactions at/above `MISSING_RECEIPT_THRESHOLD` (default 75)
  with no linked attachment (QuickBooks `Attachable`).
- Present as a checklist of "attach a receipt to these" — the user uploads in QuickBooks. The
  assistant does not upload receipts in v1.

## Confirmation protocol (the heart of write-back)

Any QuickBooks mutation (v1: categorizing a transaction) follows this exact sequence:

1. **Propose** — show the user the precise change: which transaction, current state → proposed
   state (e.g. *"TXN 4821, $240 to 'Acme Hosting' → categorize as 'Software & Subscriptions'?"*).
2. **Confirm** — get an explicit yes for that item, or an explicit yes to a clearly-listed batch.
   - *"fix everything"* / *"categorize them all"* is NOT enough on its own — first present the full
     list of proposed changes, then ask the user to approve that reviewed list.
   - Silence, ambiguity, or "looks good" on a partial view → do not write; ask again.
3. **Re-read** — immediately before writing, re-fetch the record. If it changed since the scan,
   re-propose instead of writing stale data.
4. **Write** — apply the single approved change via the QuickBooks connector.
5. **Report** — confirm what was written, with the new state. Track it for the summary's
   "resolved this session" count.

Never batch-write past what the user explicitly approved. Never write during a scheduled
(automation) run — automations are read-only and notify only.

## The accountant-ready summary

Built from `close_scan.py` output (+ anything resolved this session). Contents:

- **Header** — company, period (explicit range), generated date.
- **P&L snapshot** — income, expenses, net, from `pnl_snapshot`.
- **Close readiness** — counts: uncategorized remaining, open AR, open AP, duplicate candidates,
  missing receipts.
- **AR aging** — the bucket table + total outstanding.
- **AP aging** — the bucket table + total owed.
- **Resolved this session** — what the user approved and we wrote.
- **Open items / blockers** — what still needs a human decision before close.

Every number traces to the scan output. The summary must reconcile (e.g. AR bucket sum =
total outstanding). If the script's `totals` don't tie out, say so — do not paper over it.

## AR reminders (Gmail)

Eligibility is decided by `reminders_due.py` (deterministic, reads live balances). The agent
drafts and sends; it never invents who to chase.

- **Trigger** (per policy `first_trigger`): `on_due` (send when due date reached), `days_after:N`
  (N days overdue), or `days_before:N` (N days before due). Default `on_due`.
- **Recipient:** the invoice's billing email from QuickBooks. Missing → skip + flag (rule 10).
- **Drafting (agent judgment):** a polite, professional email. Include customer name, invoice
  number, amount due, due date, and a clear "please arrange payment" ask. Keep it short and warm.
  Mirror the customer's language if known. Do NOT include internal notes or other customers' data.
- **Send → log:** send via Gmail, then immediately upsert the `ar_reminders` ledger row
  (`stage`, `attempts`+1, `last_reminder_at`, `first_reminder_at` if first). One send per stage (rule 7).
- **Kill switch:** if `reminders_enabled` is false, do nothing (rule 6).

## Auto-chase escalation

A follow-up when a reminded invoice is still unpaid.

- **Fires only when:** first reminder sent ≥ `escalation_days` ago (default 7), invoice still unpaid
  (re-verified at send time), and `attempts < max_attempts` (default 3). `reminders_due.py` enforces this.
- **Tone shifts up:** firmer and more urgent than the first reminder, while staying professional —
  reference that a prior reminder was sent, restate the overdue amount and how many days overdue,
  and propose a concrete next step (e.g. "please confirm a payment date this week").
- **Stop conditions:** paid (→ ledger `status = paid`), disputed, opted out, or max attempts reached.
  After the last attempt, surface the invoice in the close checklist / Slack for human follow-up.

## Accountant summary email

After a close run, deliver the accountant-ready summary as a **2-page PDF** rendered from the scan.

1. Run `close_scan.py`, save its JSON.
2. Render: `accountant_summary.py <scan_json> <out.pdf> "<company>" "<accountant_email>"` — every
   number comes from the scan JSON (single source of truth).
3. **Deliver in chat** (upload the PDF) AND **email it to `accountant_email`** via Gmail with a short
   covering note (period, net, count of open items). If `accountant_email` is unset, show it in chat
   and ask whom to send it to — then remember it.

**What the PDF contains** (the renderer uses the scan's *detail*, not just aggregates):
- **Page 1 — at a glance:** branded header + "prepared for/by" line · an auto-generated **executive
  summary** sentence · **KPI cards** (Net income with MoM delta · AR outstanding · *Overdue* AR ·
  Items to fix) · a **color-coded AR-aging bar chart** (90+ in red) · a **close-readiness split** that
  separates blockers (uncategorized/duplicates/missing — red if >0) from informational counts (open
  AR/AP, overdue) so open AR is never miscolored as a problem.
- **Page 2 — detail & actions:** the **open-invoice table** (customer · invoice# · due · status ·
  amount, overdue first), **duplicate clusters** spelled out, **missing receipts**, and a
  **recommended-actions** list mirroring the in-chat CTAs.

Design rules: empty sections collapse to a one-line note (e.g. "No open payables") — never print a
zero-filled table. If a true $0 (e.g. no expenses) is correct, label it so it reads as intentional,
not missing. If `totals.ties_out` is false, the PDF prints a visible warning instead of hiding it.

## Slack alerts for blockers

After a close scan (and after a reminder run), if anything critical was found, post a concise alert
to the configured Slack channel so it isn't buried in a report.

- **Critical = any of:** overdue AR (any invoice `days_overdue > 0`), uncategorized transactions,
  duplicate candidates. (Missing receipts are included if `slack_include_missing_receipts` is true.)
- **Message:** one short block — period, the headline numbers, and a one-line call to action
  ("open a chat to review/fix"). Link the sheet/summary if available. Don't paste full tables.
- Slack alerts are notifications, not actions — they never substitute for the gated fix flow.

## Reminder ledger & policy

### `ar_reminders` tab (the ledger)
```
invoice_id, customer, billing_email, doc_number, invoice_date, due_date, amount,
stage, attempts, first_reminder_at, last_reminder_at, status, opted_out, notes
```
- `stage`: `none` | `first` | `escalation`
- `attempts`: integer count of reminders sent for this invoice
- `status`: `open` | `paid` | `disputed` | `stopped`
- `opted_out`: `TRUE` | `FALSE` (per-customer suppression)
- One row per invoice; the agent upserts it after each successful send. The script only reads it.

### Settings (skill settings / `_settings`)
```
reminders_enabled   (the kill switch; default false until policy approved)
reminder_policy     JSON: {first_trigger, escalation_days, max_attempts, business_days_only}
accountant_email
slack_channel
gmail_sender        (the from identity for outbound mail)
ar_ledger_sheet_id
```
The user approves `reminder_policy` once (critical rule 11); changing it is a normal settings edit.

## Output & delivery

- **v1: in chat.** Render the checklist and summary inline in the conversation, in the flow.
- **Scheduled monthly automation:** runs the scan read-only, posts the summary + checklist. It
  does NOT make writes and does NOT prompt for fixes (no user present to confirm). It can say
  *"N transactions need categorizing — open a chat with me to review and fix them."*
- **(planned) Base44 app view:** a workspace app that reads the same computed close data via API
  for a richer, drill-down view. Design the scan output to be app-consumable (structured JSON).

## Guardrails

### Data integrity
- **Scan returns nothing / empty period** → say the period looks empty; confirm the range/company.
- **A number doesn't tie out** (aging sum ≠ total) → surface the discrepancy; don't hide it.
- **Token expired / QuickBooks API error** → report the failure plainly; don't fabricate results.

### Writes
- **User says "fix everything"** → present the full reviewed list first, then ask for approval.
- **Record changed since scan** → re-read and re-propose; never write stale state.
- **Any uncertainty about consent** → default to NOT writing; ask again.

### Scope
- **Asked to pay a bill / send a reminder / lock the period** → out of scope; explain what the
  assistant does instead (surface + summarize).
- **Asked to resolve a duplicate / upload a missing receipt** → the assistant *flags* these but
  does not void/merge or upload in v1; direct the user to do it in QuickBooks (or, for a duplicate
  void, use the Confirmation protocol only if a gated void action has been added).
- **Asked about the Base44 app view** → planned, not built yet; say it's coming.
- **Non-QuickBooks accounting system** → out of scope.
