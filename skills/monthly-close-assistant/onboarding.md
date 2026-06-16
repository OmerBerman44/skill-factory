# Monthly Close Assistant — first-run onboarding

First activation only. Idempotent — skip any step whose artifact already exists. Because this skill
sends email on the user's behalf, **no customer email goes out until the reminder policy is approved
and the kill switch is on** (step 6).

## Detect the path

- **PATH A** — the user already asked for a close ("close my books"). Set up silently, then run the
  close in the same turn (read-only — no reminders until policy is approved).
- **PATH B** — conversational only ("what can you do?"). Briefly introduce, then set up.

## Setup steps

1. **Verify connectors.** Need: **QuickBooks** (always), **Gmail** (reminders + summary email),
   **Slack** (alerts), **Google Sheets** (reminder ledger). If any are missing, list them and ask
   the user to connect in Settings → Integrations. QuickBooks is required to do anything; the others
   gate their specific features (e.g. no Slack → skip alerts, don't block the close).
2. **Identify the company.** If multiple QuickBooks companies, ask which (store `company_id`); else use the one.
3. **Confirm close basics** (ask once, infer where possible):
   - Fiscal year start (default: January / calendar year).
   - Home currency (read from QuickBooks preferences if available).
   - When to run the monthly close automation (default: the 3rd of each month, 09:00 local).
4. **Create the AR reminder ledger.** Create a Google Sheet (or a tab `ar_reminders` in an existing
   Bookkeeping sheet) with the canonical columns in § Schemas. Store its id as `ar_ledger_sheet_id`.
5. **Capture the accountant email.** Ask: *"Where should I send the close summary each month?"*
   Store as `accountant_email` (can be the user themselves). Also set `gmail_sender` (the from identity).
6. **Approve the reminder policy (one-time consent — REQUIRED before any send).** Walk the user
   through and store `reminder_policy` = `{first_trigger, escalation_days, max_attempts,
   business_days_only}`. Recommend defaults: first reminder `on_due`, escalate after `7` days, max
   `3` attempts, business days only. Explain plainly: *"With this on, I'll automatically email
   customers polite reminders when invoices are due and follow up if unpaid — I always re-check the
   balance first and never chase a paid invoice. You can pause me anytime."* Only when the user
   agrees, set `reminders_enabled = true`. If they decline, leave it `false` (close + summary still work).
7. **Set the Slack channel.** Ask which channel/DM for blocker alerts; store `slack_channel`.
8. **Install the automations:**
   - **Monthly close** (default 3rd, 09:00): runs the close read-only → emails the accountant summary
     PDF → Slack-alerts on blockers. Store its id.
   - **Daily AR reminders** (e.g. weekdays 10:00, only if `reminders_enabled`): runs `reminders_due.py`
     → sends eligible reminders/escalations → logs the ledger → Slack one-liner. Store its id.
9. **Capability briefing** (one combined message): what runs automatically (monthly summary email,
   Slack alerts, daily reminders if enabled), what they can ask for ("close my books", "send
   reminders now", "pause reminders"), and how to pause (*"pause reminders"* flips the kill switch).

## Termination rule

Onboarding is complete once QuickBooks is verified, `company_id` is known, and the `ar_reminders`
ledger exists. (Reminder policy can be approved later; until then, `reminders_enabled` stays false.)
On subsequent activations, go straight to normal operation — don't re-introduce or re-ask.

## Schemas

### `ar_reminders` (the reminder ledger)
```
invoice_id, customer, billing_email, doc_number, invoice_date, due_date, amount,
stage, attempts, first_reminder_at, last_reminder_at, status, opted_out, notes
```
- `stage`: `none` | `first` | `escalation`  ·  `status`: `open` | `paid` | `disputed` | `stopped`
- `opted_out`: `TRUE` | `FALSE`  ·  one row per invoice; the agent upserts after each send.

### Settings keys
```
company_id, fiscal_year_start, home_currency,
ar_ledger_sheet_id, accountant_email, gmail_sender, slack_channel,
reminder_policy (JSON), reminders_enabled (bool kill switch),
close_automation_id, reminder_automation_id
```

## Recovery cases

- **QuickBooks disconnected** → ask to reconnect; don't scan.
- **Gmail/Slack/Sheets disconnected** → disable just that feature and tell the user; keep the rest working.
- **Reminder ledger deleted** → recreate it (step 4) and set `reminders_enabled = false` until the
  user re-confirms (don't resume sending against lost history).
- **An automation missing** → silently reinstall it next activation.
- **User says "pause reminders" / "stop chasing"** → set `reminders_enabled = false` immediately.
- **User says "reset"** → confirm first, then start fresh without destroying old data.
