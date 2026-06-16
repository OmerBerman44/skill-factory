# Skill QA — review rubric

The full rubric. `SKILL.md` routes here. The review has four dimensions; work them in order. Combine
your judgment findings with `lint.py`'s mechanical findings into one prioritized report. Every finding
cites the [SKILL-AUTHORING.md](../SKILL-AUTHORING.md) rule it breaks.

---

## Dimension A — API / integration layer

The connector calls are where a skill silently corrupts data or fabricates results. Read every script
and every place `SKILL.md`/`reference.md` describes an API call. Check:

### Auth & inputs
- **Tokens/secrets come from env, never hardcoded.** A literal token, key, or account id in source is a
  `BLOCKER`. (Spec §6 *Deterministic scripts: contract* — "read inputs from args + env".)
- **Required inputs fail loudly.** Missing token / id / arg → a clear error + non-zero exit, not a silent
  default or a `None` that flows downstream. (§6.)
- **Reads are header-based, not positional**, when parsing user data (sheets, CSVs) — columns get
  renamed. Positional indexing into user data is a `WARN`. (§6.)

### Correctness of the calls
- **Pagination is handled.** A list query that reads one page and assumes it's complete is a `BLOCKER`
  for any data that can exceed a page (invoices, transactions). Look for `STARTPOSITION`/`MAXRESULTS`,
  `pageToken`, `nextPage` loops.
- **Response shapes are defensive.** `(x or {}).get(...)` over `x[...]`; nested fields guarded. A raw
  `resp["a"]["b"]` on an external payload is a `WARN`.
- **Errors are surfaced, not swallowed.** Non-200s must raise/exit with the status + a slice of the body,
  not return empty and let the agent "find nothing". (See `close_scan.py`'s `qb_query_page`.)
- **Money/dates are computed in code**, never via spreadsheet formulas or LLM arithmetic. (§1.)

### Read-only vs gated-write discipline (the safety core)
- **Scripts are read-only unless proven otherwise.** A script that mutates the user's data in a loop is a
  `BLOCKER` — writes that need consent belong in the agent, gated. The docstring should say "READ-ONLY".
  (§6 *Deterministic reads & gated writes*.)
- **Every write the skill performs is consent-gated.** Trace each mutation to a Confirmation protocol
  (propose → explicit consent → re-read → write one → report). A bulk write on "do it all" without
  showing the list first is a `BLOCKER`. (§6.)

### `# VERIFY` markers
- **Integration code not yet tested against a live account carries a `# VERIFY`** saying what to confirm.
  An untested query/response-shape with *no* marker is a `BLOCKER` (it reads as known-good when it isn't).
- `lint.py` counts the markers; you judge whether the *risky* lines actually carry one. Every marker is a
  known production blocker the author must clear or call out. (§6 *`# VERIFY` markers*.)

---

## Dimension B — Flow / architecture

Does the skill hold together as a contract? Check against §6 conventions and the §7 ship-gate:

- **Prose/script split is correct.** Pixel/format-exact output or numbers-that-must-tie-out done in prose
  → `BLOCKER` (belongs in a script). "Decide if this is a refund" encoded in code → `WARN` (belongs in
  prose). (§1, §2 pattern 2.)
- **Critical-rules block present** — 3–5 imperative invariants near the top of `SKILL.md`, ending with the
  "**these rules win**" clause. Missing/absent clause → `WARN`. (§6.)
- **Confirmation protocol exists** wherever the skill writes — explicit, with re-read-before-write. (§6.)
- **Automation silence rule** is explicit *if* the skill runs on a schedule: "when automation-triggered,
  NEVER message the user." Scheduled skill with no silence rule → `BLOCKER` (it'll spam the user). (§6.)
- **Onboarding is idempotent, self-healing, with a termination rule** *if* the skill is stateful. Missing
  termination rule (it re-onboards forever) → `WARN`. Not self-healing (breaks if an artifact is deleted)
  → `WARN`. (§6 pattern 3.)
- **Progressive disclosure holds.** `SKILL.md` is a small router; heavy detail lives in sidecars. A bloated
  `SKILL.md` (lint flags the size) that inlines full rules → `WARN`. (§3.)
- **"Don't recreate the script" guard** — every script has an `agent_rule.md` entry naming it and saying
  "run it, don't reimplement". A script with no guard → `WARN` (the model will rewrite it). (§6 pattern 6.)
- **Scope hygiene** — required connectors listed; an explicit **out-of-scope** list. No out-of-scope list →
  `WARN` (the skill improvises into the wrong product). (§6.)

---

## Dimension C — Completeness / actionable CTAs (Pattern 7 — the value check)

This is what separates a skill that produces an artifact from one that delivers an outcome. The whole
point of the factory's Pattern 7. Check:

- **Every terminal output offers or triggers a next action.** A skill that generates a report/summary/
  result and stops there — no email, no status update, no reminder, no "want me to…" — is a `BLOCKER` on
  value: *the workflow is incomplete*. (§6 *Complete workflow — actionable CTAs*; §7 Value group.)
- **Each CTA maps to a real connector** the skill actually has. A CTA offering an action with no backing
  connector → `WARN` (false promise).
- **Auto-triggered CTAs are gated** by an approved policy + kill switch; anything outbound/destructive that
  fires without consent → `BLOCKER`. Until a policy is approved, an auto-CTA must be downgraded to suggested.
- **Automation-run CTA behavior is defined** — on a no-user run, only pre-approved auto-CTAs fire; the rest
  are queued/surfaced. A skill that would send blind on a schedule → `BLOCKER`.
- **The list is ranked and capped (2–4)** and led by the highest-leverage step. Ten unranked CTAs → `NIT`.
- **Improvement lens:** even when a skill has *one* CTA, ask "what's the obvious second step a user always
  takes after this output?" and suggest adding it. This is where the reviewer adds value, not just safety.

---

## Dimension D — Discovery

Will the agent actually find and trigger the skill? (§4, §7 Discovery group.)

- **`description` earns its place** — states what it does, the input it accepts, and ends with explicit
  trigger phrases (`Use when…`, `Triggers on "…"`). A vague description → `WARN` (the skill never fires).
- **`name` is kebab-case and matches the folder.** Mismatch → `BLOCKER` (won't load). (lint flags this.)
- **Trigger phrases don't dangerously over-claim** (e.g. triggering on a generic word that hijacks other
  skills) → `WARN`.

---

## Severity model

| Severity | Meaning | Examples |
|---|---|---|
| `BLOCKER` | Unsafe, wrong, or value-incomplete — must fix before ship | ungated write; hardcoded token; untested call with no `# VERIFY`; output with no next action; name≠folder |
| `WARN` | Correct today, will bite later | positional read of user data; missing out-of-scope list; no termination rule; no agent_rule guard |
| `NIT` | Polish | unranked CTA list; wording; cosmetic structure |

Be honest (critical rule 4): don't inflate, don't bury. A skill ships when there are **zero blockers** and
the author has consciously accepted each `WARN`.

---

## Report format

Emit in this shape — scannable, prioritized, every finding actionable:

```
# QA review — <skill-name>

Verdict: <SHIP | DO NOT SHIP — N blocker(s)>  ·  mechanical gate (lint): <pass|fail>

## Blockers (N)
- [A: integration] <file>:<line> — <what's wrong>. Fix: <exact change>. (spec §<x>)
- [C: CTAs] SKILL.md — output dead-ends; no next action offered. Fix: add a "Next actions" section
  with <the obvious CTA>. (spec §6 pattern 7)

## Warnings (N)
- [B: flow] <file> — <issue>. Fix: <change>. (spec §<x>)

## Nits (N)
- <file> — <polish>.

## Improvements (the value lens — optional but recommended)
- <a stronger CTA, a richer connector use, a missing automation that would complete the workflow>

## Ship-gate (§7)
Discovery ✓ · Structure ✓ · Correctness ✗ (1 ungated write) · Behavior ✓ · Value ✗ (no CTA)
```

Lead with blockers. Quote `lint.py` for every mechanical claim. End by offering the § Next actions CTAs
from `SKILL.md` (apply fixes / re-run / open the gate) — the reviewer doesn't dead-end either.
