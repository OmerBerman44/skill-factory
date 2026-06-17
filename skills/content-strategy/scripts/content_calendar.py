"""
Content Strategy — Phase 2 posting calendar (deterministic scheduler)

PATTERN 2. The agent CALLS this; it never hand-rolls the date math inline (see agent_rule.md).
Phase 2 turns the APPROVED Phase-1 brief into concrete content. This script owns the one part that
must be exact and repeatable: laying the recommended items out across a 30-day calendar at a chosen
cadence. The agent then writes the post copy (judgment) and builds the visuals in Canva (connector) —
this script writes neither copy nor assets, and it talks to no network.

Contract:
  - PURE COMPUTE. No network, no connector writes. Reads a plan/brief JSON, prints a calendar JSON.
  - Idempotent: same inputs (incl. --start) -> same calendar. Pass --start for full reproducibility;
    it defaults to today only as a convenience.
  - Fails loudly with a clear message + non-zero exit if the plan is missing/invalid or has no items.

Usage:
  python3 content_calendar.py <plan_json_path> [--start YYYY-MM-DD] [--per-week N] [--days N]
    plan_json_path — the approved brief JSON (content-strategy Stage 6 shape) OR a plan with an
                     explicit "items" list (see below). MUST carry "approved": true (boolean) — a
                     missing key, a string, or false is refused (the Phase-1 -> Phase-2 gate backstop).
    --start        — first calendar day (default: today). Pass it to make the output reproducible.
    --per-week     — posts per week (default: plan.posts_per_week, else 3). Clamped to 1..7.
    --days         — calendar length in days (default: 30).

Accepted input shapes (either works):
  A) Approved brief: { "approved": true, "push_hard":[{product,content_angle}],
       "recommended_offers":[{offer,rationale}], "seasonal_opportunities":[{theme}],
       "hold_steady":[{product}], "reposition_or_pause":[{product,action}] }
     -> items are derived with sensible priorities (push=3, offer/seasonal=2, hold/reposition=1).
  B) Explicit plan: { "approved": true, "posts_per_week": 3, "items":[ {title,type,angle,priority} ] }

Output (stdout JSON):
  {
    "window": {start, end, days}, "posts_per_week",
    "slots":   [ {date, weekday, title, type, angle} ],   # one per planned post, in date order
    "summary": {total_posts, by_type:{...}, by_item:{...}}
  }
The agent fills copy + Canva assets per slot; nothing here is published.
"""

import os
import sys
import json
import datetime as dt
from collections import OrderedDict, defaultdict

# Mon=0 .. Sun=6. Cadence patterns spread posts sensibly across the week.
CADENCE = {
    1: [1],                    # Tue
    2: [1, 3],                 # Tue, Thu
    3: [0, 2, 4],              # Mon, Wed, Fri
    4: [0, 1, 3, 4],           # Mon, Tue, Thu, Fri
    5: [0, 1, 2, 3, 4],        # weekdays
    6: [0, 1, 2, 3, 4, 5],     # Mon–Sat
    7: [0, 1, 2, 3, 4, 5, 6],  # daily
}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── ARGS ──────────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    fail("usage: content_calendar.py <plan_json_path> [--start YYYY-MM-DD] [--per-week N] [--days N]")

PLAN_PATH = sys.argv[1]


def arg_val(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else None


START = arg_val("--start")
PER_WEEK_ARG = arg_val("--per-week")
DAYS_ARG = arg_val("--days")

if not os.path.exists(PLAN_PATH):
    fail(f"plan json not found: {PLAN_PATH}")
try:
    with open(PLAN_PATH, encoding="utf-8") as fh:
        plan = json.load(fh)
except Exception as e:
    fail(f"could not parse plan json: {e}")

# Safety backstop for the Phase-1 -> Phase-2 gate: REQUIRE explicit approval. Missing key, a string
# ("true"), 0/1, or false are all refused — only the boolean true passes. The agent's transition gate
# is the primary enforcement; this makes the script refuse to build a calendar from an unapproved brief.
if not (isinstance(plan, dict) and plan.get("approved") is True):
    fail("brief is not approved — set \"approved\": true (boolean) only after the owner signs off. "
         "Phase 2 / the calendar will not run on an unapproved brief.")

try:
    start_date = dt.date.fromisoformat(START) if START else dt.date.today()
except ValueError:
    fail(f"bad --start '{START}', expected YYYY-MM-DD.")

days = int(DAYS_ARG) if DAYS_ARG and DAYS_ARG.isdigit() else 30
if days <= 0:
    fail("--days must be a positive integer.")


# ── DERIVE ITEMS ───────────────────────────────────────────────────────────────
def derive_items(plan):
    """Build the work list. Explicit plan.items wins; else derive from the brief fields."""
    if isinstance(plan.get("items"), list) and plan["items"]:
        items = []
        for raw in plan["items"]:
            if not raw.get("title"):
                continue
            items.append({
                "title": str(raw["title"]),
                "type": str(raw.get("type", "push")),
                "angle": str(raw.get("angle", "")),
                "priority": int(raw["priority"]) if str(raw.get("priority", "")).strip().lstrip("-").isdigit() else 2,
            })
        return items

    items = []

    def add(title, type_, angle, priority):
        if title:
            items.append({"title": str(title), "type": type_, "angle": str(angle or ""), "priority": priority})

    for it in plan.get("push_hard", []):
        add(it.get("product") or it.get("title"), "push", it.get("content_angle") or it.get("angle"), 3)
    for it in plan.get("recommended_offers", []):
        add(it.get("offer") or it.get("title"), "offer", it.get("rationale") or it.get("angle"), 2)
    for it in plan.get("seasonal_opportunities", []):
        add(it.get("theme") or it.get("title"), "seasonal", it.get("timing") or it.get("angle"), 2)
    for it in plan.get("hold_steady", []):
        add(it.get("product") or it.get("title"), "hold", it.get("note") or it.get("angle"), 1)
    for it in plan.get("reposition_or_pause", []):
        add(it.get("product") or it.get("title"), "reposition", it.get("action") or it.get("angle"), 1)
    return items


items = derive_items(plan)
if not items:
    fail("no content items found in the plan (need push_hard/recommended_offers/etc., or an items[] list).")

# posts/week: arg > plan > default 3, clamped to 1..7
if PER_WEEK_ARG and PER_WEEK_ARG.isdigit():
    per_week = int(PER_WEEK_ARG)
elif str(plan.get("posts_per_week", "")).strip().isdigit():
    per_week = int(plan["posts_per_week"])
else:
    per_week = 3
per_week = max(1, min(7, per_week))


# ── BUILD CALENDAR (deterministic) ───────────────────────────────────────────
def post_dates(start, days, per_week):
    """The calendar days that get a post, by a fixed weekly cadence pattern."""
    pattern = set(CADENCE[per_week])
    out = []
    for offset in range(days):
        d = start + dt.timedelta(days=offset)
        if d.weekday() in pattern:
            out.append(d)
    return out


def weighted_rotation(items):
    """Interleave items by priority so high-priority items recur more, but spread (not front-loaded).
    e.g. A(3),B(2),C(1) -> [A,B,C,A,B,A]. Deterministic: priority desc, then input order."""
    order = sorted(range(len(items)), key=lambda i: (-max(1, items[i]["priority"]), i))
    remaining = {i: max(1, items[i]["priority"]) for i in range(len(items))}
    rotation = []
    while any(v > 0 for v in remaining.values()):
        for i in order:
            if remaining[i] > 0:
                rotation.append(i)
                remaining[i] -= 1
    return rotation


dates = post_dates(start_date, days, per_week)
rotation = weighted_rotation(items)

slots = []
by_type = defaultdict(int)
by_item = defaultdict(int)
for k, d in enumerate(dates):
    it = items[rotation[k % len(rotation)]]
    slots.append({
        "date": d.isoformat(),
        "weekday": WEEKDAYS[d.weekday()],
        "title": it["title"],
        "type": it["type"],
        "angle": it["angle"],
    })
    by_type[it["type"]] += 1
    by_item[it["title"]] += 1

result = {
    "window": {
        "start": start_date.isoformat(),
        "end": (start_date + dt.timedelta(days=days - 1)).isoformat(),
        "days": days,
    },
    "posts_per_week": per_week,
    "slots": slots,
    "summary": {
        "total_posts": len(slots),
        "by_type": OrderedDict(sorted(by_type.items())),
        "by_item": OrderedDict(sorted(by_item.items(), key=lambda kv: (-kv[1], kv[0]))),
    },
}
print(json.dumps(result, indent=2))
