"""
<Skill> — <what this script renders/does> (deterministic)

PATTERN 2. This script exists because the output must be exact and repeatable —
prose instructions to an LLM are not reliable enough. The agent CALLS this script;
it never reimplements it inline (see agent_rule.md).

Contract:
  - Idempotent: running twice yields the same result.
  - Reads all inputs from args + env. Hardcodes nothing user-specific.
  - Header-based when reading user data (columns may be renamed) — never positional.
  - Fails loudly with a clear message if a required input is missing.

Usage:
  python3 render_example.py <resource_id> [mode]

Args:
  resource_id  — the user's resource (e.g. Google Sheet ID) to read/write.
  mode         — optional; <what modes mean>.

Env:
  <CONNECTOR>_ACCESS_TOKEN   (required) — fresh OAuth token with the needed scope.
"""

import os
import sys

# ── ARGS / ENV ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("<CONNECTOR>_ACCESS_TOKEN", "")
if not TOKEN:
    print("ERROR: <CONNECTOR>_ACCESS_TOKEN environment variable is required.")
    sys.exit(1)

RESOURCE_ID = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("<SKILL>_RESOURCE_ID", "")
if not RESOURCE_ID:
    print("ERROR: resource_id is required. Pass as 1st arg or set <SKILL>_RESOURCE_ID.")
    sys.exit(1)

MODE = sys.argv[2] if len(sys.argv) > 2 else "default"


# ── READ ────────────────────────────────────────────────────────────────────
def read_data():
    """Fetch the user's data. Map columns by HEADER NAME, not position."""
    # rows = fetch(...)
    # headers = rows[0]
    # col = {h.lower().strip(): i for i, h in enumerate(headers)}
    raise NotImplementedError("TODO: implement read")


# ── COMPUTE ─────────────────────────────────────────────────────────────────
def compute(data):
    """All aggregation/math happens in code, never via spreadsheet formulas."""
    raise NotImplementedError("TODO: implement compute")


# ── WRITE / RENDER ──────────────────────────────────────────────────────────
def render(result):
    """Produce the exact, deterministic output (PNG, styled sheet, file, …)."""
    raise NotImplementedError("TODO: implement render")


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print(f"<Skill> — running on {RESOURCE_ID[:12]}… (mode={MODE})")
    data = read_data()
    result = compute(data)
    render(result)
    print("  ✓ done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
