# Content Strategy — workflow examples

Concrete end-to-end walkthroughs across **both phases**. Full rules live in `reference.md`. Numbers are
illustrative of the *shape* of `sales_analysis.py` output — in a real run they come from the script.

## Example 0 — Opening a fresh session (process map + guidance)

Owner opens the skill: *"what should I post this month?"*

1. **Show the process map verbatim** (SKILL.md § Show this first), so the owner sees the two phases and the gate.
2. **Getting started:** *"To start I need (1) a sales source connected — QuickBooks or PayPal (Canva too, for
   Phase 2 — that can wait), and (2) two quick answers: rank your sellers by revenue, by how fast they sell, or
   a blend? And do you know your seasonal pattern, or should I use benchmarks for your category?"*
3. On their answers → begin Phase 1. (On an **automation** run, skip the map/guidance — silence rule.)

## Example 1 — Phase 1: SaaS, rank by revenue (happy path)

Owner: PayPal connected, picks **revenue**, no stated seasonality.

1. **Pull:** `sales_analysis.py paypal 90 --metric revenue`. Output (abridged): `data_sufficiency.sufficient:
   true` (210 days); top_performers `[Pro Plan $24k, Team Plan $9k, Onboarding Add-on $3k]`; trending_up
   `[Team Plan +38%]`; trending_down `[Starter Plan −22%]`; slow_movers `[Sticker Pack $90]`.
2. **Seasonality:** January → SaaS new-year planning (benchmark, labelled). Flag Team Plan to ride momentum.
3. **Brief (≈250 words):** Exec summary (Pro Plan is the engine; Team Plan surging +38% into Jan planning);
   Push hard Team Plan / Pro Plan / Onboarding Add-on with angles; Hold Starter Plan; Reposition Sticker Pack
   (bundle as a free perk); Seasonal: lead with annual-plan value; Offers: annual discount on Team.
4. **Approve & CTAs:** *"Match your gut? When you approve, the next step is Phase 2 — I'll create the posts.
   Want me to email the brief too?"*

## Example 2 — Phase 1: Retail, velocity, thin data (< 3 months)

QuickBooks; shop opened 7 weeks ago.

1. **Pre-flight:** company-info shows `Industry: Unknown` → ask → *"Retail"* → set via quickbooks-profile-info-update → *"Profile updated."*
2. **Clarify:** owner wants what's *moving* → **velocity**.
3. **Pull:** `sales_analysis.py quickbooks 90 --metric velocity` → `data_sufficiency.sufficient: false`
   (49 days, `recommend_benchmarks: true`); top by velocity `[Candle 6.2/wk, Mug 4.1/wk]`.
4. **Brief:** opens with *"Heads-up: only ~7 weeks of data, so this leans on retail benchmarks alongside your
   early numbers — treat it as directional."* Push fast-movers, flag the seasonal ramp, recommend a "new shop" bundle.
5. **CTAs:** approve → Phase 2; offer a monthly refresh so the brief sharpens as data grows.

## Example 3 — The transition gate (Phase 1 → Phase 2)

Continuing Example 1, owner: *"Looks great, approved — let's make them."*

1. **Don't jump into creation.** Run the transition gate (reference.md § Transition gate). Present a recap:
   > **Recap:** PayPal · ranked by revenue · 210 days (high confidence). Push: Team Plan, Pro Plan, Onboarding
   > Add-on. Offer: annual discount on Team. Season: Jan planning.
   > **Phase-2 plan:** I'll create ~13 posts (3/week for 30 days) for those 3 items + the offer, as square
   > social posts, using your logo/colors. Build them in — **Canva, Figma, Google Slides, or AI imagery via
   > Hugging Face?** (Canva's connected ✓.)
   > **Anything to change before I start creating?**
2. Owner: *"Make it 2/week, skip the Onboarding Add-on, and use Canva."* → update the plan (2/week, 2 items + offer, Canva), re-confirm.
3. Owner: *"Go."* → proceed to Phase 2. (Had the chosen tool been disconnected, you'd ask them to connect it here first.)

## Example 4 — Phase 2: create the content

From the aligned plan in Example 3 (2/week, Team Plan + Pro Plan + annual-discount offer).

1. **Draft copy** per planned post — e.g. Team Plan: hook *"Scale without the chaos,"* caption tied to the
   "+38% this quarter" angle, CTA *"Upgrade your team this week."* One block per post; no invented stats.
2. **Build assets in the chosen tool** (connector) — here Canva: a design per post with the copy + brand colors;
   return editable links. (Owner picked Figma or Google Slides? Build there instead. Want original artwork? Generate
   it via **Hugging Face** text-to-image, then drop it into the design.) If the tool errors / isn't connected →
   deliver copy + calendar and tell the owner to paste the copy in manually. Never fake a link.
3. **Calendar:** save the approved brief to `approved_brief.json`, run
   `content_calendar.py approved_brief.json --per-week 2 --start 2026-06-22`. It returns dated `slots[]`
   (push items get the most slots) — map each slot to its copy + Canva link.
4. **Present the package** for review: per post → date · format · copy · Canva link, then the calendar summary.
   *"Here's the month — tweak anything, and post them when you're ready (I don't publish for you)."*

## Example 5 — Owner wants to skip straight to creating (phase guardrail)

Owner (no brief yet): *"Just make me this month's posts."*

1. You still need an approved brief + the gate first (critical rule 2). Explain *why*, briefly: *"Two minutes
   first so the posts reflect what's actually selling — let me pull your numbers, then I'll create."*
2. Run a fast Phase 1 → brief → approval → transition gate → Phase 2. Don't fabricate a brief to shortcut.

## Example 6 — Monthly automation run (Phase 1 only, silent)

The optional monthly refresh fires (no owner in chat).

1. Run **Phase 1 only** → `sales_analysis.py` → draft brief with `approved: false`.
2. **Stay silent:** no out-of-band message, **no Phase 2**, no Canva, no email. Queue the draft so it's waiting
   for review on the owner's next visit — the queued draft IS the notification (no message is sent).
3. The owner reviews/approves later in chat — only then does the gate, and Phase 2, run.

## Example 7 — PayPal rate-limited (fallback)

`sales_analysis.py paypal 90` exits **code 2**, stderr `RATE_LIMITED` (429 after the built-in 30s retry).

1. Don't loop the script. *"PayPal is rate-limiting me — try QuickBooks instead, or build the brief from the
   chunks I already pulled?"*
2. QuickBooks → re-run (pre-flight first). Otherwise → proceed on partial data and **state the limitation** in the brief.

## Example 8 — Margin requested (unavailable)

Owner: *"Rank by profit margin."*

1. Not supported — feeds carry sale price, not cost; the script sets `requested_metric_unavailable: "margin"` and falls back to revenue.
2. *"I can't do true margin yet — your transactions don't include unit costs. I'll rank by revenue, velocity, or a blend — which?"* Proceed on their pick.

## Example 9 — Stripe source (Phase 1)

Owner sells via Stripe Checkout. Connector: Stripe; metric **revenue**.

1. **No pre-flight** (Stripe needs no profile) — just ask their category for seasonality context.
2. **Pull:** `STRIPE_ACCESS_TOKEN=… sales_analysis.py stripe 90 --metric revenue`. The script lists paid charges
   (amounts ÷100 from cents), names them from each charge's `description`/`metadata.product`; charges without one
   roll up as **"Uncategorized sale"**. `granularity: product`.
3. **Brief:** as usual. If a big chunk is "Uncategorized sale," flag it: *"~40% of revenue has no product label on
   the charge — add a description/metadata in Stripe and next month's brief gets sharper."*

## Example 10 — Plaid source (revenue by source, not products)

Owner is a service business; connects a bank account via **Plaid** (no QuickBooks/Stripe).

1. **Pull:** `PLAID_CLIENT_ID=… PLAID_SECRET=… PLAID_ACCESS_TOKEN=… sales_analysis.py plaid 90`. The script keeps
   **inflows** (deposits), grouped by payer/merchant → `granularity: revenue_source`; `products[]` are revenue
   *streams* (e.g. "Stripe Payouts", "Acme Corp ACH"), each 1 unit per deposit.
2. **Phrase the brief for sources, not products:** *"Your biggest revenue streams are Stripe payouts and direct
   ACH from Acme; deposits from Etsy are fading."* Recommendations become *which channels/clients to nurture*,
   plus the seasonal layer — not "which product to push."
3. **Be honest about the limit:** *"Plaid shows money in by who paid you, not which product sold — for
   product-level content, connect QuickBooks, Stripe, or PayPal."* Phase 2 still runs the same way on approval.
