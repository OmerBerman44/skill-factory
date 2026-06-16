# Monthly Close Assistant — workflow examples

Concrete end-to-end walkthroughs. Full rules live in `reference.md`.

## Example 1 — on-demand close ("close my books for May")

User: *"Run my monthly close for May."*

1. Resolve period → `2026-05` (May 1–31). Confirm the connected company.
2. Run `close_scan.py <company_id> 2026-05`. Output: 6 uncategorized txns, 4 open AR ($12,400),
   3 open AP ($5,200), P&L net $18,900, `ties_out: true`.
3. Present the checklist in chat, grouped:
   > **May close — 3 things to review**
   > 🟡 6 uncategorized transactions ($2,140 total)
   > 🟢 Open AR: $12,400 across 4 invoices (1 is 45 days overdue)
   > 🟢 Open AP: $5,200 across 3 bills (1 due in 4 days)
4. Offer: *"Want me to suggest categories for the 6 uncategorized transactions?"*
5. After review (Example 2), generate the accountant summary in chat. Numbers tie out to the scan.

## Example 2 — gated write-back (categorizing, with confirmation)

Continuing from Example 1, user: *"Yes, categorize them."*

1. This is a **write** → Confirmation protocol. Do NOT bulk-write on "categorize them".
2. Propose the full reviewed list first:
   > Here's what I'd set — confirm and I'll apply:
   > 1. TXN 4821 · $240 · Acme Hosting → **Software & Subscriptions**
   > 2. TXN 4830 · $86 · Sushi Yasaka → **Meals & Entertainment**
   > 3. TXN 4844 · $1,200 · (unknown payee) → *no confident suggestion — needs your input*
   > … (3 more)
3. User: *"1, 2, 4, 5 are right. Skip 3 and 6."*
4. For each approved item: re-read the transaction (rule 5), confirm it's still uncategorized,
   then write the single change via the QuickBooks connector.
5. Report: *"✅ Categorized 4 transactions. 2 still need your input (TXN 4844, TXN 4851)."*
6. Re-run the scan or decrement counts; reflect "4 resolved this session" in the summary.

## Example 3 — ambiguous consent (guardrail)

User: *"looks good"* after seeing only the first 2 of 6 proposed changes.

1. Partial view + vague approval → **do not write.**
2. Ask: *"Want me to apply all 6, or just the 2 you've seen? Here's the full list again: …"*
3. Only write the items the user explicitly approves.

## Example 4 — scheduled monthly automation (read-only, notify)

The monthly close automation fires on the 3rd at 09:00.

1. Run `close_scan.py` read-only for last month.
2. **Make no writes** — there's no user present to confirm (critical rule 1).
3. Post the summary + checklist:
   > 📋 April close is ready to review. Net $18,900. 6 transactions need categorizing,
   > $12,400 AR open (1 overdue 45d). Open a chat with me to review and fix.
4. Do not attempt fixes; the user does that interactively later.

## Example 5 — numbers don't tie out (data integrity)

Scan returns `ties_out: false` (AR aging buckets sum ≠ open AR total).

1. Do NOT paper over it. Surface it:
   > ⚠️ I found a discrepancy: open AR lists $12,400 but the aging buckets sum to $12,100.
   > I won't include AR aging in the accountant summary until this reconciles — want me to re-scan?
2. Offer a re-scan; never invent a reconciling number.

## Example 6 — duplicate candidates + missing receipts (flag, never fix)

Scan returns `duplicates: [{type:"Bill", party:"Acme Hosting", amount:240, items:[2 bills 3 days apart]}]`
and `missing_receipts: [{type:"Purchase", id:"4844", amount:1200, party:"(unknown)"}]`.

1. Surface both as review flags — these are NOT auto-fixed:
   > 🟠 Possible duplicate: 2 bills from **Acme Hosting** for **$240** dated 3 days apart
   > (Bill #1180, Bill #1186). Same charge twice, or two real bills?
   > 🟠 Missing receipt: **$1,200** Purchase on May 14 has no attachment.
2. For the duplicate: ask the user to judge. If they say "yes, void the second one" — that's a
   QuickBooks write → Confirmation protocol (and note v1's only built write is categorization;
   otherwise direct them to void it in QuickBooks).
3. For the missing receipt: it's their action — *"Attach the receipt in QuickBooks; I'll re-check
   on the next scan."* The assistant does not upload receipts in v1.
4. Both appear in the checklist and the accountant summary's "open items / blockers".

## Example 7 — accountant summary email after a close

After the close run (Examples 1–2):

1. Save the `close_scan.py` JSON to a temp file.
2. Render: `accountant_summary.py <scan.json> /app/close-summary.pdf "Acme LLC"`.
3. **Show the PDF in chat** (upload it) AND **email it** to `accountant_email` via Gmail with a short
   note: *"May close summary attached. Net $18,900; 6 items still need categorizing."*
4. If `accountant_email` is unset, just show it in chat and ask whom to send it to, then remember it.

## Example 8 — daily AR reminder run (policy-driven, automation)

The daily reminder automation fires at 10:00.

1. `reminders_enabled` is true → proceed (else stop).
2. Run `reminders_due.py <company_id> <ledger_sheet_id>`. Output `to_send`: 3 first reminders
   (incl. the $5,000 invoice due Jun 30 — `on_due` trigger) + 1 escalation.
3. For each: re-verify it's still unpaid, draft a **polite** email to the billing email
   (customer, invoice #, amount, due date, "please arrange payment"), send via Gmail.
4. Log each to `ar_reminders` (stage=first, attempts=1, timestamps).
5. Post a Slack one-liner: *"Sent 4 AR reminders ($11,200 outstanding). 1 was a follow-up."*
   No chat message to the user (automation run).

## Example 9 — auto-chase escalation

An invoice reminded 8 days ago is still unpaid; policy escalates after 7, max 3.

1. `reminders_due.py` returns it with `stage: "escalation"`, `prior_attempts: 1`.
2. Re-verify unpaid. Draft a **firmer, higher-urgency** follow-up: references the earlier reminder,
   restates the amount + days overdue, asks for a concrete payment date this week.
3. Send via Gmail; update ledger to `stage=escalation`, `attempts=2`.
4. After `attempts` hits `max_attempts`, stop sending and surface it in the next close checklist /
   Slack for human follow-up — don't keep emailing.

## Example 10 — paid in between (the critical guardrail)

A reminder was queued, but the customer paid this morning.

1. `reminders_due.py` pulls live balances — the now-paid invoice has Balance 0, so it isn't in
   `to_send` at all.
2. If it somehow surfaced, the send-time re-verify (rule 8) catches Balance 0 → **do not send**;
   mark the ledger `status = paid`. Never chase a paid invoice.

## Example 11 — kill switch / pause

User: *"pause the reminders."*

1. Set `reminders_enabled = false`. Confirm: *"Paused — I won't send any reminders or follow-ups
   until you say resume."*
2. The daily automation still fires but exits immediately while the switch is off. Close + summary
   + Slack alerts keep working.
