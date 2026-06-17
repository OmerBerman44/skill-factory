# Content Strategy — Square integration (planned, NOT built)

**Status: stubbed.** `sales_analysis.py source=square` exits with code **3** today. This document is the
implementation spec for the Square path so it can be added without re-deriving the design. Until it's
built and verified against a live Square account, the skill supports **QuickBooks and PayPal only** — if
an owner is on Square, tell them it's coming and offer one of the supported connectors.

## Why Square is different

Unlike QuickBooks (company-scoped) and PayPal (account-scoped), Square sales are **scoped to locations**.
A merchant can have many locations, and orders/payments are queried per location. So the pull is two-step:
discover locations, then pull orders for each.

## Planned fetch path

1. **Discover locations.** The platform exposes a generic Square call (the skill's spec calls it
   `make_api_request`):

   ```
   make_api_request(service="locations", method="list")   # → Square Locations API: GET /v2/locations
   ```

   Keep every `location.id` with `status = "ACTIVE"`.  # VERIFY: Locations response shape + status enum.

2. **Pull orders per location.** For each location id, search orders in the window via the Orders API
   (`POST /v2/orders/search`), paginating on `cursor`:

   ```
   make_api_request(service="orders", method="search", body={
     "location_ids": [<id>],
     "query": {"filter": {"date_time_filter": {"created_at": {"start_at": <ISO>, "end_at": <ISO>}}},
               "sort": {"sort_field": "CREATED_AT"}},
     "cursor": <next cursor or omitted>
   })
   ```

   - **Window:** same `<lookback_days>` as the other sources.  # VERIFY: `created_at` is the right filter field.
   - **Pagination:** loop while the response returns a `cursor`.  # VERIFY: cursor field name + termination.
   - **Status:** count completed sales only.  # VERIFY: which `state` values (e.g. `COMPLETED`) realize revenue,
     and whether to net out returns/refunds.

3. **Normalize line items.** Each order's `line_items[]` → the same shape the ranking math consumes:

   | normalized field | Square source | notes |
   |---|---|---|
   | `name`     | `line_item.name`                              | fallback "Unnamed item" |
   | `revenue`  | `line_item.total_money.amount` / 100          | Square money is **integer minor units** — divide by 100. # VERIFY |
   | `quantity` | `line_item.quantity` (string → float)         | # VERIFY: quantity is a string |
   | `date`     | order `created_at` (date portion)             | window-filter on this |
   | `currency` | `total_money.currency`                        | |

4. **Hand to the existing math.** Once normalized, the rows feed the **same** `aggregate()` / `rank()`
   functions — no new ranking logic. Square only adds a fetch adapter (`fetch_square()`), keeping a single
   source of truth for the numbers.

## Implementation checklist (when this is built)

- [ ] Add `SQUARE_ACCESS_TOKEN` (and `SQUARE_API_BASE`, default `https://connect.squareup.com`) to the env contract.
- [ ] Replace the `fetch_square()` stub with the locations → orders pull above; paginate every list call.
- [ ] Surface non-200s loudly (status + body slice) and exit non-zero, like the QuickBooks/PayPal paths.
- [ ] Clear every `# VERIFY` here against a live Square sandbox, then production.
- [ ] Update `SKILL.md` (move Square out of "planned"), `reference.md` § connector notes, and add a
      Square worked example to `examples.md`.
- [ ] Re-run `skill-qa/scripts/lint.py` and the judgment review before shipping the Square path.

## Money & correctness reminders

- Square amounts are **integer minor units** (cents) — divide by 100 exactly once, in the adapter, not in prose.
- Refunds/returns: decide explicitly whether to net them out; document the choice. Don't silently ignore them.
- The adapter stays **READ-ONLY** — Square is a data source here; the skill never writes to it.
