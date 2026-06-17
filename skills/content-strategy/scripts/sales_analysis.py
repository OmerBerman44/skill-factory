"""
Content Strategy — sales analysis (deterministic read + math)

PATTERN 2. The agent CALLS this; it never re-implements the ranking/trend math inline
(see agent_rule.md). This script does the read-only, deterministic part of the strategy:
pull the period's sales from the chosen connector and compute the performance signals
(top performers, slow movers, momentum, data sufficiency). The agent reasons over the JSON,
layers in seasonality (judgment), writes the 30-day brief, and gets owner approval.

Contract:
  - READ-ONLY. This script makes NO writes to any connector, ever. It only GETs.
  - Idempotent: same source + window + data -> same output (no randomness).
  - Every figure the agent puts in the brief comes from this output ("never invent a number").
  - Fails loudly with a clear message + non-zero exit if a required input is missing.
  - Rate-limited (PayPal 429): pause once, retry once, then exit code 2 ("RATE_LIMITED") so the
    agent can apply the documented fallback (switch connector / use what was pulled). The judgment
    of *what to do next* is the agent's; the deterministic retry is here.

Sources split into two granularities:
  - PRODUCT-level (quickbooks, paypal, stripe, square): revenue per product/service.
  - REVENUE-SOURCE level (plaid): bank inflows grouped by payer/merchant — no product names or
    quantities. The output's "granularity" field tells the agent which, so the brief adapts its
    language ("products" vs "revenue sources").

Usage:
  python3 sales_analysis.py <source> <lookback_days> [--metric revenue|velocity|margin|combined]
    source         — quickbooks | paypal | stripe | plaid | square
    lookback_days  — integer window, e.g. 90. Trend compares the most recent
                     TREND_WINDOW_DAYS against the prior TREND_WINDOW_DAYS.

Env (source-specific; only the chosen source's vars are required):
  PayPal:
    PAYPAL_ACCESS_TOKEN     (required) — fresh OAuth2 token, transaction-search scope.
    PAYPAL_API_BASE         (optional) — default https://api-m.paypal.com (sandbox:
                                         https://api-m.sandbox.paypal.com).
  QuickBooks:
    QUICKBOOKS_ACCESS_TOKEN (required) — fresh OAuth2 token, read scope.
    QUICKBOOKS_COMPANY_ID   (required) — QBO realmId / company id.
    QUICKBOOKS_API_BASE     (optional) — default https://quickbooks.api.intuit.com.
    QUICKBOOKS_MINOR_VERSION(optional) — default 75.
  Stripe:
    STRIPE_ACCESS_TOKEN     (required) — secret/restricted key or Connect access token (Bearer).
    STRIPE_API_BASE         (optional) — default https://api.stripe.com.
  Plaid:
    PLAID_CLIENT_ID         (required) — Plaid client id.
    PLAID_SECRET            (required) — Plaid secret for the environment.
    PLAID_ACCESS_TOKEN      (required) — the item access token for the linked account.
    PLAID_API_BASE          (optional) — default https://production.plaid.com.
  Tunables (optional, all sources):
    TREND_WINDOW_DAYS  (default 30)  — recent-vs-prior comparison window for momentum.
    TOP_N              (default 5)   — how many top performers to surface.
    SLOW_N             (default 5)   — how many slow movers to surface.
    TREND_THRESHOLD    (default 15)  — +/- % change to call something trending up/down.
    COMBINED_REV_WEIGHT(default 0.6) — weight on revenue in the "combined" metric (rest -> velocity).
    SUFFICIENT_DAYS    (default 90)  — data span below this -> recommend industry benchmarks.

Note: --metric margin is accepted but DOWNGRADED to revenue (cost data isn't in the feeds); the
output then carries "requested_metric_unavailable": "margin". `line_count` is the number of sale
LINES rolled into a product, NOT a count of distinct orders/transactions.

Output: a single JSON object on stdout (the single source of truth for the brief):
  {
    "source", "granularity": "product"|"revenue_source",
    "window":{start,end,lookback_days,trend_window_days}, "metric",
    "requested_metric_unavailable": null | "margin",
    "currency", "currencies":[...], "mixed_currency": bool, "margin_available": false,
    "totals": {gross_revenue,total_units,product_count,line_count},
    "data_sufficiency": {sufficient,days_of_data,months_of_data,recommend_benchmarks},
    "products":      [ {name,revenue,units,line_count,velocity_per_week,
                        first_seen,last_seen,recent_revenue,prior_revenue,trend_pct,trend} ],
    "top_performers":[ ...ranked by metric... ],
    "slow_movers":   [ ...lowest revenue among items that sold, excluding top_performers... ],
    "trending_up":   [ ...biggest positive momentum above threshold... ],
    "trending_down": [ ...biggest negative momentum below -threshold... ]
  }
  If mixed_currency is true, gross_revenue/per-product revenue blend currencies (no FX conversion).

Connector query strings / response shapes are marked `# VERIFY` where they must be confirmed
against a live account before production. Grep for VERIFY before ship.
"""

import os
import sys
import json
import time
import datetime as dt
from collections import defaultdict

# `requests` is imported lazily inside the connector functions so the CLI's input
# validation, the Square stub, and the pure ranking math run without the HTTP dependency.

# ── ARGS / ENV ──────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("ERROR: usage: sales_analysis.py <source:quickbooks|paypal|stripe|plaid|square> "
          "<lookback_days> [--metric revenue|velocity|margin|combined]", file=sys.stderr)
    sys.exit(1)

SOURCE = sys.argv[1].strip().lower()

try:
    LOOKBACK_DAYS = int(sys.argv[2])
    if LOOKBACK_DAYS <= 0:
        raise ValueError
except ValueError:
    print(f"ERROR: lookback_days must be a positive integer, got '{sys.argv[2]}'.", file=sys.stderr)
    sys.exit(1)

METRIC = "revenue"
if "--metric" in sys.argv:
    i = sys.argv.index("--metric")
    if i + 1 < len(sys.argv):
        METRIC = sys.argv[i + 1].strip().lower()
if METRIC not in ("revenue", "velocity", "margin", "combined"):
    print(f"ERROR: --metric must be revenue|velocity|margin|combined, got '{METRIC}'.", file=sys.stderr)
    sys.exit(1)

TREND_WINDOW_DAYS = int(os.environ.get("TREND_WINDOW_DAYS", "30"))
TOP_N = int(os.environ.get("TOP_N", "5"))
SLOW_N = int(os.environ.get("SLOW_N", "5"))
TREND_THRESHOLD = float(os.environ.get("TREND_THRESHOLD", "15"))
COMBINED_REV_WEIGHT = float(os.environ.get("COMBINED_REV_WEIGHT", "0.6"))
SUFFICIENT_DAYS = int(os.environ.get("SUFFICIENT_DAYS", "90"))

TODAY = dt.date.today()
WINDOW_START = TODAY - dt.timedelta(days=LOOKBACK_DAYS)
RECENT_START = TODAY - dt.timedelta(days=TREND_WINDOW_DAYS)
PRIOR_START = TODAY - dt.timedelta(days=2 * TREND_WINDOW_DAYS)


def to_date(s):
    """Parse a YYYY-MM-DD (optionally with a time/zone suffix) into a date; None on failure."""
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


# ── CONNECTOR: PAYPAL (read-only) ─────────────────────────────────────────────
def fetch_paypal():
    """Pull completed sales line items from the PayPal Transaction Search API.

    Returns a list of normalized line items: {name, date, revenue, quantity, currency}.
    PayPal's Transaction Search caps each request at a 31-day range, so we chunk the window.
    """
    token = os.environ.get("PAYPAL_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: PAYPAL_ACCESS_TOKEN is required for source=paypal.", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("PAYPAL_API_BASE", "https://api-m.paypal.com")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    line_items = []

    def fetch_chunk(chunk_start, chunk_end):
        """One <=31-day chunk, paginated. Returns normalized line items from this chunk."""
        out = []
        page = 1
        while True:
            params = {
                # VERIFY: PayPal Transaction Search wants ISO-8601 with offset, e.g. 2026-01-01T00:00:00-0000.
                "start_date": f"{chunk_start.isoformat()}T00:00:00-0000",
                "end_date": f"{chunk_end.isoformat()}T23:59:59-0000",
                "fields": "transaction_info,cart_info",  # VERIFY: cart_info carries item_details.
                "page_size": 500,                          # VERIFY: 500 is the documented max.
                "page": page,
            }
            r = _paypal_get(f"{base}/v1/reporting/transactions", headers, params)
            body = r.json()
            details = body.get("transaction_details", [])          # VERIFY: top-level key.
            for txn in details:
                info = txn.get("transaction_info", {}) or {}
                # Only count money-in (completed sales). VERIFY: status 'S' = success; event/credit-debit codes.
                status = info.get("transaction_status", "S")
                if status not in ("S", "P", "V"):  # VERIFY: which statuses count as a realized sale.
                    continue
                amt = ((info.get("transaction_amount") or {}).get("value"))
                currency = (info.get("transaction_amount") or {}).get("currency_code", "")
                txn_date = to_date(info.get("transaction_initiation_date", ""))
                cart = (txn.get("cart_info") or {}).get("item_details", [])  # VERIFY: cart_info shape.
                if cart:
                    for item in cart:
                        out.append({
                            "name": (item.get("item_name") or "Unnamed item").strip(),
                            "date": txn_date,
                            "revenue": _money((item.get("item_amount") or {}).get("value")),
                            "quantity": _qty(item.get("item_quantity")),
                            "currency": currency,
                        })
                else:
                    # No itemized cart (common for simple payments) -> bucket as one line.
                    out.append({
                        "name": (info.get("transaction_subject")            # VERIFY: best label field.
                                 or info.get("paypal_reference_id")
                                 or "Uncategorized sale").strip(),
                        "date": txn_date,
                        "revenue": _money(amt),
                        "quantity": 1.0,
                        "currency": currency,
                    })
            total_pages = int(body.get("total_pages", 1) or 1)      # VERIFY: pagination field.
            if page >= total_pages or not details:                  # secondary guard: stop on an empty page
                break
            page += 1
        return out

    # Chunk the full window into <=31-day spans (PayPal constraint).  # VERIFY: 31-day cap.
    span_start = WINDOW_START
    while span_start <= TODAY:
        span_end = min(span_start + dt.timedelta(days=30), TODAY)
        line_items.extend(fetch_chunk(span_start, span_end))
        span_start = span_end + dt.timedelta(days=1)
    return line_items


def _paypal_get(url, headers, params):
    """GET with one rate-limit retry. 429 twice -> exit 2 (RATE_LIMITED) for the agent to handle."""
    import requests
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 429:
        time.sleep(30)                       # documented: pause once, retry once
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 429:
            print("RATE_LIMITED: PayPal returned 429 after one retry.", file=sys.stderr)
            sys.exit(2)
    if r.status_code != 200:
        print(f"ERROR: PayPal request failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return r


# ── CONNECTOR: QUICKBOOKS (read-only) ─────────────────────────────────────────
def fetch_quickbooks():
    """Pull invoice + sales-receipt line items from QuickBooks Online.

    Returns normalized line items: {name, date, revenue, quantity, currency}.
    """
    token = os.environ.get("QUICKBOOKS_ACCESS_TOKEN", "")
    company_id = os.environ.get("QUICKBOOKS_COMPANY_ID", "")
    if not token or not company_id:
        print("ERROR: QUICKBOOKS_ACCESS_TOKEN and QUICKBOOKS_COMPANY_ID are both required for "
              "source=quickbooks.", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("QUICKBOOKS_API_BASE", "https://quickbooks.api.intuit.com")
    minor = os.environ.get("QUICKBOOKS_MINOR_VERSION", "75")  # VERIFY: current QBO minorversion.
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    start, end = WINDOW_START.isoformat(), TODAY.isoformat()
    import requests

    def query_all(base_query, key):
        out, pos = [], 1
        page = 1000
        while True:
            q = f"{base_query} STARTPOSITION {pos} MAXRESULTS {page}"  # VERIFY: 1-indexed STARTPOSITION.
            r = requests.get(f"{base}/v3/company/{company_id}/query", headers=headers,
                             params={"query": q, "minorversion": minor})
            if r.status_code != 200:
                print(f"ERROR: QuickBooks query failed ({r.status_code}): {r.text[:300]}",
                      file=sys.stderr)
                sys.exit(1)
            batch = r.json().get("QueryResponse", {}).get(key, [])
            out.extend(batch)
            if len(batch) < page:
                return out
            pos += page

    line_items = []
    # VERIFY: Invoice + SalesReceipt carry the sales lines; SalesItemLineDetail.{ItemRef,Qty}.
    for entity, key in (("Invoice", "Invoice"), ("SalesReceipt", "SalesReceipt")):
        rows = query_all(
            f"SELECT * FROM {entity} WHERE TxnDate >= '{start}' AND TxnDate <= '{end}'", key)
        for doc in rows:
            doc_date = to_date(doc.get("TxnDate", ""))
            currency = (doc.get("CurrencyRef") or {}).get("value", "")  # VERIFY: currency field.
            for line in doc.get("Line", []):
                if line.get("DetailType") != "SalesItemLineDetail":
                    continue
                detail = line.get("SalesItemLineDetail", {}) or {}
                name = (detail.get("ItemRef") or {}).get("name", "Unnamed item")
                line_items.append({
                    "name": (name or "Unnamed item").strip(),
                    "date": doc_date,
                    "revenue": _money(line.get("Amount")),
                    "quantity": _qty(detail.get("Qty", 1)),
                    "currency": currency,
                })
    return line_items


# ── CONNECTOR: STRIPE (read-only) ─────────────────────────────────────────────
def fetch_stripe():
    """Pull paid charges from Stripe in the window. Product-level when the charge carries a
    description / product metadata; otherwise one 'Uncategorized sale' line (like PayPal).

    Returns normalized line items: {name, date, revenue, quantity, currency}.
    """
    token = os.environ.get("STRIPE_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: STRIPE_ACCESS_TOKEN is required for source=stripe.", file=sys.stderr)
        sys.exit(1)
    import requests
    base = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com")
    headers = {"Authorization": f"Bearer {token}"}
    # Stripe filters `created` by Unix seconds. VERIFY: tz handling — date->epoch uses local tz here.
    start_ts = int(dt.datetime(WINDOW_START.year, WINDOW_START.month, WINDOW_START.day).timestamp())
    end_ts = int(dt.datetime(TODAY.year, TODAY.month, TODAY.day, 23, 59, 59).timestamp())

    line_items = []
    params = {"created[gte]": start_ts, "created[lte]": end_ts, "limit": 100}  # VERIFY: 100 = max.
    while True:
        r = requests.get(f"{base}/v1/charges", headers=headers, params=params)
        if r.status_code != 200:
            print(f"ERROR: Stripe request failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        body = r.json()
        data = body.get("data", [])               # VERIFY: list payload under "data".
        for ch in data:
            if ch.get("paid") is False or ch.get("status") == "failed":
                continue                          # count realized sales only. VERIFY: status values.
            # Stripe amounts are in the currency's MINOR units (cents). VERIFY: zero-decimal
            # currencies (JPY etc.) are NOT /100 — handle if those accounts appear.
            revenue = round((ch.get("amount", 0) or 0) / 100.0, 2)
            created = ch.get("created")
            date = dt.date.fromtimestamp(created) if created else None
            name = (ch.get("description")
                    or (ch.get("metadata") or {}).get("product")     # VERIFY: product metadata key.
                    or "Uncategorized sale")
            line_items.append({
                "name": str(name).strip() or "Uncategorized sale",
                "date": date,
                "revenue": revenue,
                "quantity": 1.0,
                "currency": (ch.get("currency") or "").upper(),
            })
        if body.get("has_more") and data:         # VERIFY: cursor pagination via starting_after.
            params["starting_after"] = data[-1].get("id")
        else:
            break
    return line_items


# ── CONNECTOR: PLAID (read-only) ──────────────────────────────────────────────
def fetch_plaid():
    """Pull bank INFLOWS from Plaid, grouped later by payer/merchant. This is REVENUE-SOURCE
    granularity — there are no product names or quantities, so each inflow is one unit.

    Returns normalized line items: {name, date, revenue, quantity, currency}.
    """
    client_id = os.environ.get("PLAID_CLIENT_ID", "")
    secret = os.environ.get("PLAID_SECRET", "")
    access_token = os.environ.get("PLAID_ACCESS_TOKEN", "")
    if not (client_id and secret and access_token):
        print("ERROR: PLAID_CLIENT_ID, PLAID_SECRET and PLAID_ACCESS_TOKEN are all required for "
              "source=plaid.", file=sys.stderr)
        sys.exit(1)
    import requests
    base = os.environ.get("PLAID_API_BASE", "https://production.plaid.com")

    line_items, offset, count = [], 0, 500
    while True:
        body = {
            "client_id": client_id, "secret": secret, "access_token": access_token,
            "start_date": WINDOW_START.isoformat(), "end_date": TODAY.isoformat(),
            "options": {"count": count, "offset": offset},          # VERIFY: offset pagination.
        }
        r = requests.post(f"{base}/transactions/get", json=body)
        if r.status_code != 200:
            print(f"ERROR: Plaid request failed ({r.status_code}): {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        payload = r.json()
        txns = payload.get("transactions", [])
        for t in txns:
            amt = t.get("amount", 0) or 0
            # Plaid convention: POSITIVE = money OUT of the account, NEGATIVE = money IN. Revenue is
            # the inflows. VERIFY: confirm sign convention for this account/product before production.
            if amt >= 0:
                continue
            line_items.append({
                "name": (t.get("merchant_name") or t.get("name") or "Unknown source").strip(),
                "date": to_date(t.get("date")),
                "revenue": round(-amt, 2),
                "quantity": 1.0,
                "currency": (t.get("iso_currency_code") or t.get("unofficial_currency_code") or ""),
            })
        total = int(payload.get("total_transactions", len(txns)) or len(txns))
        offset += len(txns)
        if offset >= total or not txns:
            break
    return line_items


def fetch_square():
    """Square is a documented future enhancement, not yet implemented in this script."""
    print("ERROR: source=square is not yet supported by sales_analysis.py. The full integration "
          "path (locations discovery, orders pull, line-item normalization) is documented in "
          "reference/square-integration.md. Use source=quickbooks or source=paypal for now.",
          file=sys.stderr)
    sys.exit(3)


# ── NORMALIZE HELPERS ─────────────────────────────────────────────────────────
def _money(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


def _qty(v):
    try:
        q = float(v)
        return q if q > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


# ── AGGREGATION + SIGNALS (deterministic math) ────────────────────────────────
def aggregate(line_items):
    """Roll line items up per product name and compute revenue/units/velocity/momentum."""
    weeks_in_window = max(LOOKBACK_DAYS / 7.0, 1.0)
    by_product = defaultdict(lambda: {
        "revenue": 0.0, "units": 0.0, "line_count": 0,
        "recent_revenue": 0.0, "prior_revenue": 0.0,
        "first_seen": None, "last_seen": None,
    })

    for it in line_items:
        d = it.get("date")
        if d is None or d < WINDOW_START or d > TODAY:
            continue  # never count outside the window
        p = by_product[it["name"]]
        p["revenue"] += it["revenue"]
        p["units"] += it["quantity"]
        p["line_count"] += 1  # count of sale LINES (not distinct orders) — see reference.md schema
        if d >= RECENT_START:
            p["recent_revenue"] += it["revenue"]
        elif d >= PRIOR_START:
            p["prior_revenue"] += it["revenue"]
        p["first_seen"] = d if p["first_seen"] is None else min(p["first_seen"], d)
        p["last_seen"] = d if p["last_seen"] is None else max(p["last_seen"], d)

    products = []
    for name, p in by_product.items():
        recent, prior = round(p["recent_revenue"], 2), round(p["prior_revenue"], 2)
        if prior > 0:
            trend_pct = round((recent - prior) / prior * 100.0, 1)
        elif recent > 0:
            trend_pct = None  # new/no-baseline: momentum exists but % is undefined
        else:
            trend_pct = 0.0
        if trend_pct is None:
            trend = "new"
        elif trend_pct >= TREND_THRESHOLD:
            trend = "up"
        elif trend_pct <= -TREND_THRESHOLD:
            trend = "down"
        else:
            trend = "flat"
        products.append({
            "name": name,
            "revenue": round(p["revenue"], 2),
            "units": round(p["units"], 2),
            "line_count": p["line_count"],
            "velocity_per_week": round(p["units"] / weeks_in_window, 2),
            "first_seen": p["first_seen"].isoformat() if p["first_seen"] else None,
            "last_seen": p["last_seen"].isoformat() if p["last_seen"] else None,
            "recent_revenue": recent,
            "prior_revenue": prior,
            "trend_pct": trend_pct,
            "trend": trend,
        })
    return products


def rank(products, metric):
    """Rank by the chosen metric. 'combined' = min-max blend of revenue + velocity."""
    sold = [p for p in products if p["revenue"] > 0 or p["units"] > 0]

    def key_revenue(p):
        return p["revenue"]

    def key_velocity(p):
        return p["velocity_per_week"]

    if metric == "combined":
        rev_max = max((p["revenue"] for p in sold), default=0.0) or 1.0
        vel_max = max((p["velocity_per_week"] for p in sold), default=0.0) or 1.0
        w = COMBINED_REV_WEIGHT
        for p in sold:
            p["_combined"] = round(w * (p["revenue"] / rev_max)
                                   + (1 - w) * (p["velocity_per_week"] / vel_max), 4)
        ranked = sorted(sold, key=lambda p: p["_combined"], reverse=True)
    elif metric == "velocity":
        ranked = sorted(sold, key=key_velocity, reverse=True)
    else:  # revenue (and the margin fallback)
        ranked = sorted(sold, key=key_revenue, reverse=True)

    top = [dict(p) for p in ranked[:TOP_N]]
    # Slow movers: lowest revenue among items that actually sold (low-momentum candidates).
    # Exclude anything already in top_performers so a small catalog can't put the same product in
    # both "Push hard" and "Reposition or pause" (the SMB-with-few-SKUs case).
    top_names = {t["name"] for t in top}
    slow = [dict(p) for p in sorted(sold, key=key_revenue) if p["name"] not in top_names][:SLOW_N]

    movers_up = sorted([p for p in sold if p["trend"] == "up"],
                       key=lambda p: (p["trend_pct"] or 0), reverse=True)
    movers_down = sorted([p for p in sold if p["trend"] == "down"],
                         key=lambda p: (p["trend_pct"] or 0))
    return top, slow, movers_up[:TOP_N], movers_down[:TOP_N]


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    if SOURCE == "paypal":
        line_items = fetch_paypal()
    elif SOURCE == "quickbooks":
        line_items = fetch_quickbooks()
    elif SOURCE == "stripe":
        line_items = fetch_stripe()
    elif SOURCE == "plaid":
        line_items = fetch_plaid()
    elif SOURCE == "square":
        fetch_square()  # exits
        return 3
    else:
        print(f"ERROR: unknown source '{SOURCE}'. Use quickbooks | paypal | stripe | plaid | square.",
              file=sys.stderr)
        sys.exit(1)

    # Plaid returns bank inflows grouped by payer/merchant — no products/quantities. Everything else
    # is product/service level. The agent uses this to phrase the brief correctly.
    granularity = "revenue_source" if SOURCE == "plaid" else "product"

    products = aggregate(line_items)

    # Data sufficiency: span actually observed in the pulled data.
    dates = [to_date(p["first_seen"]) for p in products if p["first_seen"]] + \
            [to_date(p["last_seen"]) for p in products if p["last_seen"]]
    if dates:
        days_of_data = (max(dates) - min(dates)).days + 1
    else:
        days_of_data = 0
    sufficient = days_of_data >= SUFFICIENT_DAYS

    requested_unavailable = "margin" if METRIC == "margin" else None
    effective_metric = "revenue" if METRIC == "margin" else METRIC

    top, slow, up, down = rank(products, effective_metric)

    # Currencies seen in the data. Revenue is summed in raw amounts WITHOUT FX conversion, so if more
    # than one currency is present the totals blend currencies — flag it so the agent says so and does
    # not present a single-currency total as exact (this MVP does no FX conversion; see reference.md).
    currencies = sorted({it["currency"] for it in line_items if it.get("currency")})
    mixed_currency = len(currencies) > 1
    currency = currencies[0] if len(currencies) == 1 else ("MIXED" if mixed_currency else "")

    result = {
        "source": SOURCE,
        "granularity": granularity,
        "window": {
            "start": WINDOW_START.isoformat(),
            "end": TODAY.isoformat(),
            "lookback_days": LOOKBACK_DAYS,
            "trend_window_days": TREND_WINDOW_DAYS,
        },
        "metric": effective_metric,
        "requested_metric_unavailable": requested_unavailable,
        "margin_available": False,  # cost data isn't in these transaction feeds; see reference.md.
        "currency": currency,
        "currencies": currencies,
        "mixed_currency": mixed_currency,
        "totals": {
            "gross_revenue": round(sum(p["revenue"] for p in products), 2),
            "total_units": round(sum(p["units"] for p in products), 2),
            "product_count": len(products),
            "line_count": sum(p["line_count"] for p in products),
        },
        "data_sufficiency": {
            "sufficient": sufficient,
            "days_of_data": days_of_data,
            "months_of_data": round(days_of_data / 30.0, 1),
            "recommend_benchmarks": not sufficient,
        },
        "products": sorted(products, key=lambda p: p["revenue"], reverse=True),
        "top_performers": top,
        "slow_movers": slow,
        "trending_up": up,
        "trending_down": down,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
