# Content Strategy — agent rules

## Always check the skill before acting

For ANY "what should I post / promote / what's selling / content plan / make my content" task:
1. Read `content-strategy/SKILL.md` first.
2. On a fresh session, show the process map + getting-started guidance before asking for anything.
3. Follow the documented two-phase procedure exactly — do NOT write inline code that duplicates either script.

## The numbers come from the scripts, never from you

- DO NOT compute top sellers, slow movers, velocity, or momentum by hand or inline, and DO NOT eyeball the
  connector's raw JSON to rank products. Run `sales_analysis.py` and reason over its JSON.
- DO NOT hand-roll the posting calendar dates. Run `content_calendar.py` on the approved brief.
- If a figure is not in `sales_analysis.py` output, it does not go in the brief. Never fabricate a number,
  a price, a stat, or a testimonial — in the brief OR in Phase-2 copy.
- Seasonality, content angles, offers, and the post copy ARE your judgment — layer them on the scripts' output.

## Two phases, one gate — never jump ahead

- Phase 1 (Prep) produces the strategy brief; Phase 2 (Create) produces copy + assets (in the owner's chosen
  tool: Canva / Figma / Google Slides / Hugging Face) + the calendar.
- **Never start Phase 2** until the brief is **approved** AND the owner has **aligned at the transition gate**
  (recap + Phase-2 plan + explicit go). Even if the owner says "just make the posts," run a fast Phase 1 + the gate first.
- On the monthly **automation** run: Phase 1 only, draft brief, stay silent. NO Phase 2, NO asset creation, NO email.

## Drafts until approved; the skill creates, it does not publish

- The brief is a draft (`approved: false`) until the owner approves it; Phase-2 copy/assets are drafts to review.
- Never email, share, publish, post, or auto-fire a CTA without explicit owner sign-off.
- The skill does NOT post to social, schedule in third-party tools, or run ads — the owner publishes when ready.

## Writes are gated and minimal

- Only two writes exist: (a) the QuickBooks **Industry** pre-flight via **quickbooks-profile-info-update**
  (exactly the owner's value — propose, confirm, report; never overwrite a populated industry), and
  (b) creating assets in the owner's chosen design tool (**Canva / Figma / Google Slides / Hugging Face**),
  only after the transition-gate go, surfaced for review.
- Confirm each live tool connector's surface before relying on it (Canva / Figma / Google Slides / Hugging
  Face) — treat the calls as unverified until tested.
- `sales_analysis.py` is READ-ONLY; `content_calendar.py` is pure compute (no network, no writes).

## Scripts exist, don't recreate them

- `sales_analysis.py` — pulls the window's sales from **QuickBooks** (`Invoice`/`SalesReceipt`), **Stripe**
  (`/v1/charges`, cents÷100), **PayPal** (Transaction Search, ≤31-day chunks, built-in 429 retry), or **Plaid**
  (bank inflows, grouped by payer → `granularity: revenue_source`, NOT products); rolls up per item and computes
  revenue / units / `velocity_per_week` / momentum, plus ranked `top_performers`, `slow_movers`, `trending_up/down`,
  and `data_sufficiency`. READ-ONLY. Square exits 3. Check `granularity` and phrase the brief accordingly
  ("products" vs "revenue streams"). Run at the start of every Phase 1.
- `content_calendar.py` — takes the APPROVED brief JSON and lays its items across a 30-day calendar at a
  chosen cadence (priority-weighted, deterministic). Pure compute; refuses an unapproved brief. Run in Phase 2.

If a ranking or the calendar looks wrong, **re-run the script** (both are idempotent) — don't recompute inline.
Check `data_sufficiency` / `requested_metric_unavailable` before doubting a number.
