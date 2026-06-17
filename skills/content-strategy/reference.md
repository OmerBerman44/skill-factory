# Content Strategy — operating reference

The full rules for the two-phase pipeline. `SKILL.md` routes here.

- **Phase 1 — Prep:** `clarify → pre-flight → pull & rank (script) → seasonality (judgment) → brief → approve`.
- **Transition gate:** recap + Phase-2 plan + explicit owner go (no creation before this).
- **Phase 2 — Create:** `draft copy (judgment) → build Canva assets (connector) → posting calendar (script) → review`.

The exact, repeatable parts are owned by scripts — rankings by `sales_analysis.py`, calendar dates by
`content_calendar.py`. Everything fuzzy (seasonality, content angles, copy, offer design) is the agent's.

---

## Stage 1 — Clarify priorities & metrics

Settle two things up front (the § Getting started questions in `SKILL.md`):

- **How to rank "top performers":**
  - `revenue` — total money in over the window. The default; what most owners mean.
  - `velocity` — units sold per week (`velocity_per_week`). Surfaces fast-moving, lower-ticket items.
  - `combined` — a min-max blend of revenue + velocity (default 0.6 revenue / 0.4 velocity, tunable via `COMBINED_REV_WEIGHT`).
  - `margin` — **not available** (see § Margin). Offer revenue / velocity / combined instead.
- **Known seasonality:** if the owner knows their pattern, capture it in their words and weight against it.
  If not, you'll use labelled category benchmarks (§ Seasonality).

If the owner expresses no preference, default to `revenue` and say so.

## Stage 2 — Pre-flight (QuickBooks only)

- Read the profile via **company-info**; check `Industry`.
- Missing / "Unknown" → ask the owner, then set it via **quickbooks-profile-info-update** with exactly the
  value they gave, and confirm. Gated, minimal write (critical rule 4); never overwrite a populated industry
  without asking.
- Stripe / PayPal / Plaid / Square: no profile — ask the owner's category in chat so seasonality has context.

## Stage 3 — Pull & rank (the script)

**Owned by `scripts/sales_analysis.py`.** Never compute rankings, velocity, or momentum inline. Always:

```bash
python3 .agents/skills/content-strategy/scripts/sales_analysis.py <source> <lookback_days> --metric <metric>
```

- **Window:** default **90 days**. The script reports the true span in `data_sufficiency`; pass 90 even for
  young businesses — it counts only what exists.
- **What it computes** (deterministically, so the brief ties out): per-product revenue, units, `line_count`
  (sale *lines*, not orders), `velocity_per_week`, `first_seen`/`last_seen`, recent-vs-prior revenue and the
  resulting `trend_pct` + `trend` (`up`/`down`/`flat`/`new`), plus ranked `top_performers`, `slow_movers`
  (lowest revenue among items that sold, **excluding** anything already in `top_performers`), `trending_up`,
  `trending_down`, and `data_sufficiency`. Don't narrate `line_count` as "orders".
- **Momentum:** "recent" = last `TREND_WINDOW_DAYS` (default 30); "prior" = the 30 days before. No prior but
  recent sales → `trend: "new"` (emerging, not "down").
- **Granularity** (`granularity` in the output): `product` for QuickBooks / Stripe / PayPal / Square — the
  `products[]` are real products/services. `revenue_source` for **Plaid** — the entries are *bank inflows
  grouped by payer/merchant*, with no product names and no real quantities. **Phrase the brief to match:** say
  "products" for product-level sources and "revenue streams / who's paying you" for Plaid. Don't claim
  product-level insight you don't have.

### Connector-specific fetch notes

- **QuickBooks:** queries `Invoice` + `SalesReceipt` lines in the window (paginated via `STARTPOSITION`/
  `MAXRESULTS`), rolls up `SalesItemLineDetail` by item name. Pre-flight must have run.
- **Stripe:** lists paid **charges** (`/v1/charges`, `created` window, cursor pagination via `starting_after`).
  Amounts are in the currency's **minor units → divided by 100**. Product name = the charge `description` or
  `metadata.product`; charges without one become a single "Uncategorized sale" line (like PayPal). Itemized
  product breakdown (Stripe Billing/Checkout line items) is a future enhancement.
- **PayPal:** Transaction Search in **≤31-day chunks** (PayPal's cap), each paginated. Itemized carts become
  per-item lines; simple payments with no cart become one "Uncategorized sale" line — surface those as
  "untagged revenue", don't invent a product name.
- **PayPal rate-limiting:** HTTP 429 → the script pauses 30s and retries **once**; still limited → exit **2**,
  `RATE_LIMITED` on stderr. Surface it and offer a fallback (another source, or the brief on data already pulled).
  Don't loop the script. (Stripe/Plaid have no special retry — a non-200 exits **1** with the status + body.)
- **Plaid:** `POST /transactions/get` (client_id + secret + access_token in the body; offset pagination). Keeps
  only **inflows** (Plaid's sign convention: negative `amount` = money in) as revenue, grouped by
  `merchant_name`/`name`. No products, no real quantities (each inflow = 1 unit) → `granularity: revenue_source`.
  Best for service businesses or as a cross-check; for product-level insight prefer QuickBooks/Stripe/PayPal.
- **Square:** exits **3** (not built) — see `reference/square-integration.md`.

### Margin

`margin_available` is always `false` in this MVP: the feeds carry sale price, not cost, so a margin ranking
would be fabricated. If margin was requested the script sets `requested_metric_unavailable: "margin"` and
falls back to `revenue`; tell the owner and say which metric you used. (Future: QuickBooks Item cost.)

## Stage 4 — Seasonality (judgment)

Layer seasonality **on top of** the script's ranking — it changes emphasis/timing, never the numbers.

- **Owner-provided patterns win.** Ramp the relevant products *before* their spike, wind down after.
- **Category benchmarks (fallback), always labelled:**
  - **Retail / e-commerce:** Q4 gift ramp from Oct; post-holiday Jan lull; back-to-school late summer.
  - **Professional services:** Q1 strong for tax/finance; new-budget buying early fiscal year; summer slowdown.
  - **SaaS / subscriptions:** Jan planning + budget cycles; renewal pushes near fiscal year-end; summer dip.
  - **Food / hospitality:** holidays and local events; weather-driven swings.
- **Timing flags.** Call out what should ramp up/down in the next 30 days — that forward call is the value.

## Stage 5 — The 30-day brief

From the script's JSON + the seasonality layer. **200–400 words**, ranked, plain-spoken:

- **Executive summary** (1–2 sentences): best sellers, the momentum story, the seasonal shift.
- **Push hard** (top 2–3): each with a *content angle* (judgment) and a *reason* that cites a script number.
- **Hold steady** (middle): keep visible, no heavy lift.
- **Reposition or pause** (slow / trending down): discount, bundle with a top seller, or pause — be specific.
- **Seasonal opportunities** (next 30 days): what to position for now.
- **Recommended offers**: 1–3 concrete plays, each justified by the data.

Every quantitative claim traces to the script. If `data_sufficiency.sufficient` is false, open with a
one-line confidence caveat and lean on benchmarks (critical rule 5).

### Brief output JSON (Phase-1 result; the input to Phase 2)

```json
{
  "period_days": 30,
  "source": "paypal|quickbooks",
  "metric_used": "revenue|velocity|combined",
  "confidence": "high|low",
  "executive_summary": "…",
  "push_hard":   [ {"product": "…", "reason": "<cites a script number>", "content_angle": "…"} ],
  "hold_steady": [ {"product": "…", "note": "…"} ],
  "reposition_or_pause": [ {"product": "…", "action": "discount|bundle|pause", "reason": "…"} ],
  "seasonal_opportunities": [ {"theme": "…", "timing": "next 30 days", "source": "owner|benchmark"} ],
  "recommended_offers": [ {"offer": "…", "applies_to": ["…"], "rationale": "…"} ],
  "approved": true
}
```

`approved` is `true` only after the owner signs off. Phase 2 (and `content_calendar.py`) **refuse** to act
on a brief with `approved: false`.

## Transition gate (Phase 1 → Phase 2)

The hand-off from prep to creation is a **deliberate checkpoint**, not an automatic step (critical rule 2).
Its job: make sure the owner is fully aligned before any content is made. Present three things, then wait
for an explicit go:

1. **Recap of what we gathered** — source + window, the metric used, the approved *push / hold / reposition*
   items and *offers*, the seasonality basis (owner vs. benchmark), and the confidence level. One screen.
2. **The Phase-2 plan** — exactly what you'll create:
   - which items get content (default: the *push hard* items + the *recommended offers* + any seasonal theme),
   - how many posts and the **cadence** (default 3/week over 30 days → ~13 posts),
   - the **formats** (e.g. Instagram/Facebook square posts, a story) — ask if unsure,
   - any **brand inputs** (logo, colors, tone) the owner wants reflected,
   - **which design tool** to build in — **Canva**, **Figma**, **Google Slides**, or AI imagery via
     **Hugging Face** (default to Canva unless the owner prefers another) — and that it's **connected**
     (if not, ask them to connect it now — Phase 2 can't build assets without it).
3. **Explicit go.** Ask *"Want me to start creating? Anything to change about the plan first?"* Only proceed on
   a clear yes. If the owner changes scope (fewer items, different formats, different tool), update the plan and re-confirm.

Surface the recap as a short summary the owner can eyeball — this is the moment to catch a wrong product or
the wrong season before effort is spent. Never skip straight from an approved brief into asset creation.

## Phase 2 — Create

Runs **only after** the transition gate. Three parts; keep everything a reviewable draft (critical rule 3).

### 2a. Draft the post copy (judgment)

For each planned item/offer, write the actual copy — this is your judgment, not a script:
- a **headline/hook**, a short **caption** (on the owner's voice and the brief's *content_angle*), and a clear **CTA**;
- mirror the customer's language/tone if known; keep claims consistent with the data (don't promise a discount the owner didn't approve);
- one copy block per planned post. Do **not** fabricate testimonials, prices, or stats — if you need a number, use one from the brief.

### 2b. Build the assets (connector — owner's chosen tool)

Turn each copy block into an editable design using the tool agreed at the gate. Pick by what the owner has
and what fits the format:

- **Canva** — fastest path to branded social posts (templates + brand kit). The default for most SMBs.
- **Figma** — for owners/teams who already design in Figma; create frames/components they can refine.
- **Google Slides** — slide decks, carousel-style posts, and simple shareable graphics; great for Google Workspace users.
- **Hugging Face** — generate **original imagery** from a text prompt (text-to-image inference) or copy
  variants; use it to produce a visual that then goes into Canva/Figma/Slides, or as a standalone image.

Rules that apply to **all** of these:
- Asset creation **writes to the owner's account** (a new Canva design, a Figma file/frame, a Slides deck, or a
  generated image) → it is a **gated** action: only after the transition-gate go, and surfaced for review afterward.
  Return the editable **links** (or the image) so the owner can tweak.
- **VERIFY:** the live tool surfaces are **unverified** — confirm each connector's actual tools before relying on
  them: Canva (create-design / autofill / brand-kit + template/brand IDs), Figma (create file/frame), Google
  Slides (`presentations.create` + `batchUpdate`), Hugging Face (Inference API endpoint + the model id, e.g. a
  text-to-image model, via `HUGGINGFACE_API_TOKEN`). Treat the exact calls as unverified until tested live.
- If the chosen tool isn't connected or a call fails: stop the asset step, report it plainly, and still deliver
  the copy + calendar (the owner can paste the copy into the tool manually). Never invent a design URL or image.
- Don't mix tools silently — build in the one the owner picked; offer a switch if it isn't working.

### 2c. Lay out the posting calendar (the script)

**Owned by `scripts/content_calendar.py`.** Never hand-roll the dates. Feed it the approved brief:

```bash
python3 .agents/skills/content-strategy/scripts/content_calendar.py <approved_brief.json> \
  [--start YYYY-MM-DD] [--per-week 3] [--days 30]
```

- It derives items from the brief (push=priority 3, offer/seasonal=2, hold/reposition=1) — or from an explicit
  `items[]` plan — and spreads them across the window at the chosen cadence, weighting higher-priority items.
- Output `slots[]` = `{date, weekday, title, type, angle}` per planned post, plus a `summary`. Pass `--start`
  for a reproducible calendar. It **refuses** any brief/plan that does not carry `"approved": true` (a missing
  key, a string, or `false` all exit 1) — the secondary backstop for the Phase-1 → Phase-2 gate.
- Map each slot to its copy block (and its asset) when you present the package.

### 2d. The content package (Phase-2 output)

Present, for review: a short intro, then per post → **date · format · copy · asset link**, followed by the
calendar `summary` (posts by type/item). Make clear it's a draft set the owner can tweak, and that **they
publish when ready** — the skill does not post. Iterate on request.

## Confirmation protocol (the gated writes)

Two writes, each gated:

1. **QuickBooks Industry (pre-flight):** propose → confirm → **quickbooks-profile-info-update** with exactly
   the owner's value → report *"Profile updated."* Never overwrite a populated industry without asking.
2. **Asset creation (Phase 2):** in the owner's chosen tool (Canva / Figma / Google Slides / Hugging Face),
   only after the transition-gate go. Create the designs, then surface the links for review. If the owner
   wants changes, adjust and re-create; don't mass-produce past the agreed plan.

No other writes, ever — no posting, no ads, no third-party scheduling.

## Guardrails (gotchas & edge cases)

### Data quality
- **Empty / near-empty window** → say so; confirm the right connector/company is connected. Don't manufacture a brief.
- **Thin data (< ~3 months)** → `data_sufficiency.sufficient: false`; open with a caveat, lean on benchmarks (rule 5).
- **Lots of "Uncategorized sale" / "Unnamed item"** → report as untagged revenue; don't invent names. Suggest adding item names.
  (Common on **Stripe** charges with no description and on **PayPal** simple payments.)
- **Plaid = revenue by source, not products** (`granularity: revenue_source`) → frame the brief around revenue
  streams / who's paying, not "products". If the owner needs product-level insight, suggest QuickBooks/Stripe/PayPal.
- **Mixed currencies** → if `mixed_currency` is true, totals blend currencies with no FX conversion (`currencies` lists them).
  Say so; don't present `gross_revenue` as an exact single-currency figure.
- **A number looks off** → trust the script output and say what you see; never patch a figure by hand.

### Connector / system
- **Missing token / company id / Plaid creds** → script exits non-zero with a clear message; relay it, ask to reconnect.
- **PayPal 429 (exit 2)** → offer the fallback; one retry only (the script already did it).
- **Stripe / Plaid non-200 (exit 1)** → relay the status + message; offer another source. (No special retry.)
- **Square requested (exit 3)** → planned, not built; point to `reference/square-integration.md`.
- **Chosen design tool not connected / call fails (Phase 2)** → deliver copy + calendar; tell the owner to connect
  the tool (Canva / Figma / Google Slides / Hugging Face) or paste the copy in manually. Never fake an asset link.

### Phase / scope / safety
- **Owner wants to jump straight to creating** ("just make the posts") → you still need an approved brief and the
  transition-gate alignment first (rule 2). Run a fast Phase 1, then the gate — explain why (so the content reflects what's actually selling).
- **Owner asks you to publish / schedule in a social tool / run ads** → out of scope; you *create*, they post.
- **Owner asks to rank by margin** → unavailable (§ Margin); offer revenue / velocity / combined.
- **No approval / no gate go** → never start Phase 2, never create assets, never email/share (rule 3).

## Known risks before ship (clear these against live accounts)

Integration points that are structurally written but **not yet verified against a live account** — each is a
production blocker until confirmed:

- **Connector API shapes in `sales_analysis.py`** — every `# VERIFY` marker, across all live sources:
  PayPal (Transaction Search fields/pagination/31-day cap); QuickBooks (`Invoice`/`SalesReceipt` lines,
  `STARTPOSITION`, currency); **Stripe** (`/v1/charges` shape, `starting_after` pagination, minor-units ÷100,
  zero-decimal currencies, date→epoch tz); **Plaid** (`/transactions/get` offset pagination and the
  inflow **sign convention** — negative = money in). Grep `# VERIFY` and clear each against a sandbox, then production.
- **Phase-2 design-tool surfaces (§2b)** — described in prose, not code, and **unverified**. Confirm each before
  relying on asset creation: **Canva** (create-design / autofill / brand-kit + template/brand IDs), **Figma**
  (create file/frame), **Google Slides** (`presentations.create` + `batchUpdate`), **Hugging Face** (Inference
  API endpoint + model id via `HUGGINGFACE_API_TOKEN`). Until verified, Phase-2 assets are best-effort — always
  be ready to fall back to copy + calendar only.
- **Square** — not built (`reference/square-integration.md`).
