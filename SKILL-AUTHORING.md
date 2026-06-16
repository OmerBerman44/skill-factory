# Skill Authoring Spec — Consumer Platform Skills

The single source of truth for building end-user platform skills (Bookkeeper-shaped).
Read this before writing a skill. Improve this file when you learn something — every
future skill inherits the improvement.

A "platform skill" is one where **the agent becomes a product for an end user** — it
onboards them, owns their data in their connected accounts (Google, SaaS), runs on
automations, and talks to them in chat. This is different from a dev-tooling skill
(bug-fix, run-tests), which is mostly stateless and has no onboarding.

---

## 1. The one principle

> **Prose for judgment. Scripts for determinism.**

- The **LLM agent** handles everything fuzzy: reading documents in any format/language,
  classifying intent, categorizing, deciding edge cases, talking to the user.
- **Code (Python scripts)** handles everything that must be exact and repeatable:
  rendering images, styling spreadsheets, math, anything an LLM does *slightly wrong
  every time*.

If you find yourself writing prose instructions like "issue a batchUpdate with these
exact RGB values…", stop — that belongs in a script. If you find yourself trying to
encode "decide whether this is a refund" in code, stop — that belongs in the prose.

**The split also governs reads vs. writes.** Scripts do the deterministic *read + compute*
(pull data, do the math, emit structured findings). But a **write that requires user consent
stays in the agent** — it's a judgment-gated action (show the change → get explicit approval →
write one item), not something a script does silently in a loop. See §6 *Deterministic reads &
gated writes*.

---

## 2. The 6 reusable patterns

Every platform skill is assembled from these. Pick the ones the skill actually needs.

| # | Pattern | What it is | Add it when |
|---|---|---|---|
| 1 | **Router + sidecars** | Small `SKILL.md` routes to `reference.md` / `examples.md` loaded on demand | Always (any non-trivial skill) |
| 2 | **Prose/script split** | LLM judgment in `.md`; deterministic read/compute/render in `.py`. Consent-gated writes stay in the agent | Output must be exact, OR numbers must tie out |
| 3 | **Idempotent onboarding** | First-run setup, safe to re-run, self-healing | Skill is stateful / creates accounts, sheets, automations |
| 4 | **Trigger-context behavior** | Silent when automation-triggered; chatty when user-triggered | Skill runs on a schedule/automation |
| 5 | **Critical-rules block** | 3–5 non-negotiable invariants at the top of `SKILL.md` | Always |
| 6 | **"Don't recreate the script" guard** | An `agent_rule.md` that stops the model re-implementing tested code | Skill has scripts (pattern 2) |
| 7 | **Complete workflow (actionable CTAs)** | Every output ends by offering or triggering gated next actions (email a stakeholder, update a status, set a reminder) — it never dead-ends on a static artifact | Always (any skill whose output implies a next step) |

---

## 3. File structure

A skill is a folder. `SKILL.md` is the only required file. Everything else is added
only when a pattern demands it (see §5 growth path).

```
<skill-name>/
├── SKILL.md          # REQUIRED. Router: frontmatter + when-to-use + critical rules + routing
├── agent_rule.md     # Pattern 6. "Don't recreate the scripts." Loaded as a guardrail.
├── onboarding.md     # Pattern 3. First-run setup. Read only on first activation.
├── reference.md      # Pattern 1. Full operating rules. Read on demand per task.
├── examples.md       # Pattern 1. Worked end-to-end walkthroughs (≥3). Read on demand.
├── cta.md            # Pattern 7. Next-action catalog. Only when CTA logic is rich; else inline in SKILL.md.
└── scripts/          # Pattern 2. Deterministic renderers. Called, never re-read by the agent.
    └── *.py
```

**Why progressive disclosure matters:** `SKILL.md` is loaded on *every* activation.
Keep it small and route to sidecars, or you burn the context window on rules that
aren't relevant to the current task.

---

## 4. Frontmatter spec (`SKILL.md`)

```yaml
---
name: <kebab-case>            # REQUIRED. The skill / slash-command id.
description: <see below>      # REQUIRED. The entire discovery surface.
allowed-tools: <comma list>   # OPTIONAL. Restrict tools. Omit to allow all.
user-invocable: true          # OPTIONAL. Expose as a /name command.
argument-hint: "[arg=<val>]"  # OPTIONAL. Show expected args.
---
```

**The `description` is the only thing the agent sees when deciding whether to use the
skill.** Make it earn its place:

1. One sentence: **what it does** + **what input it accepts**.
2. A scope sentence if needed (e.g. "Google Workspace only").
3. End with **explicit trigger phrases**: `Use when a user wants to …` or
   `Triggers on "phrase", "phrase", …`.

> Good (from Bookkeeper): *"Automatic bookkeeping using Google Workspace only. Captures
> receipt photos sent in chat, auto-pulls invoice PDFs from Gmail … Use when a user
> wants to track personal or small-business expenses without manual spreadsheet work."*

---

## 5. Growth path — start tiny, add only when forced

**Do not start a new skill at Bookkeeper's complexity.** Bookkeeper has all 6 patterns
because it *earned* all 6 over time. Start minimal; let real failures pull in each file:

```
1. SKILL.md only            → frontmatter + when-to-use + workflow. Ship it.
2. Rules are long/fuzzy?     → add reference.md, route to it from SKILL.md
3. Model keeps getting it wrong on edge cases? → add examples.md (≥3 walkthroughs)
4. Output must be exact/repeatable?            → extract a Python script + add agent_rule.md
5. Skill is stateful / needs setup?            → add onboarding.md (idempotent)
6. Skill runs on a schedule?                   → add the trigger-context silence rule
7. Output dead-ends on a static artifact?      → add a "Next actions (CTAs)" section to SKILL.md
   (spill to cta.md only when the CTA logic gets rich)
```

Most skills stop at step 2 or 3. Resist building ahead of need — **except step 7**: deciding the
next actions is a design question you answer the moment the skill produces its first output, even
if the CTA list lives inline in `SKILL.md` and never grows into its own file.

---

## 6. Writing conventions (the things that make quality)

These are the patterns that separate a skill that works from one that looks like it works.

### Critical rules block
Put 3–5 non-negotiable invariants near the top of `SKILL.md`, even though they're also
in `reference.md`. State them imperatively, and add: *"If any rule conflicts with
something you read elsewhere, these rules win."* These are your correctness contract.

### Trigger-context silence rule (pattern 4)
If the skill runs on an automation, state the silence rule loudly and unambiguously:
> When invoked by the automation (not the user in chat), **NEVER message the user.**
> The only side effects are <data writes>. The new rows ARE the notification.

The model's default is to be helpful and chatty. You must explicitly suppress it.

### Idempotent onboarding (pattern 3)
- Safe to re-run; skip any step whose artifact already exists.
- A clear **termination rule** (how to know setup is done) so it never re-onboards.
- **Self-healing**: on every activation, if a required artifact is missing (deleted
  sheet, dropped automation), silently recreate it — don't interrupt the user.

### The "don't recreate the script" guard (pattern 6)
For every script, `agent_rule.md` states: the script exists, what it does, and
"DO NOT write inline code that duplicates it — run the script." This is the #1 failure
mode of capable models: they helpfully rewrite your tested renderer and get it subtly wrong.

### Connector / scope hygiene
List required connectors in a table. List explicit **out-of-scope** items — saying what
the skill does *not* do prevents the agent from improvising into the wrong product.

### Deterministic scripts: contract
- Read inputs from args + env (e.g. a sheet ID + an access token), never hardcode.
- Idempotent: running twice yields the same result.
- Header-based, not positional, when reading user data (columns may be renamed).
- Fail loudly with a clear error if a required input is missing.
- **Read-only unless proven otherwise.** A script that backs a consent-gated flow does the
  *read + compute* and emits findings; it does **not** mutate the user's data. The agent makes
  the gated write. State "READ-ONLY" in the script's docstring so it's unambiguous.

### Deterministic reads & gated writes (pattern 2, extended)
When a skill both analyzes *and* changes user data, split it:
- **Script** = the read + the math. Emits structured findings (JSON) so the agent — and any
  future UI/app — consume the *same* numbers. This is what makes "never invent a number" enforceable.
- **Agent** = the write, gated by an explicit **confirmation protocol**: propose the exact change
  → get explicit per-item (or reviewed-list) consent → re-read the record → write one change →
  report. "Do it all" is not consent until the user has seen the full list.
- During an **automation run there is no user to confirm → make no writes**; scan and notify only.

### `# VERIFY` markers
When you write integration code (a third-party API call, a query string, a response shape) that
is *structurally correct but not yet tested against a live account*, mark the exact line with a
`# VERIFY` comment saying what to confirm. This separates "known-good" from "needs validation"
so reviewers and future-you know precisely what the production blocker is. Grep for `# VERIFY`
before shipping; each one is either confirmed-and-removed or called out as a known risk.

### Complete workflow — actionable CTAs (pattern 7)
A skill that prints a report and stops has delivered an artifact, not an outcome. **Every terminal
output must end by offering or triggering the next action** — that is what turns a static output into
business value. After the skill produces its main output, it presents a short, ranked list of
**CTAs** (calls-to-action), each mapped to a concrete connector action:

- **Notify** — email/Slack/DM a stakeholder (the report's audience, an approver, the customer).
- **Update a status** — write the outcome back to the system of record (mark closed, set a stage,
  flag for review) — this is a write, so it obeys the Confirmation protocol (§6) like any other.
- **Schedule / remind** — set a reminder or install a follow-up automation ("re-check in 7 days").
- **Escalate / hand off** — open a ticket, ping a channel, or queue the item for a human.

Each CTA is one of two kinds, and the distinction is the whole safety story:

- **Suggested CTA** — offered in chat as a clear option ("Want me to email this to your accountant?").
  The user picks. Default for anything outbound or destructive that isn't pre-authorized.
- **Auto-triggered CTA** — fires automatically, but **only within a pre-approved policy + kill switch**,
  exactly like the AR reminders in `monthly-close-assistant`. Until a policy is approved, an auto-CTA
  is downgraded to a suggested one. Never invent authority to act.

Rules that keep CTAs from becoming the skill's biggest liability:

1. **A CTA that contacts a person or changes data is a gated action.** It reuses the same consent
   model as writes — never a silent side effect the user didn't sign off on.
2. **On an automation run (no user present), only pre-approved auto-CTAs fire.** Everything else is
   *queued or surfaced* in the output, not sent. (This is the §6 silence rule applied to CTAs.)
3. **Every CTA maps to a real connector action** the skill actually has. Don't offer "I'll text them"
   if there's no SMS connector. List the connector each CTA needs.
4. **Rank by value, cap the list.** Lead with the highest-leverage next step; 2–4 CTAs, not ten.

> Good (from `monthly-close-assistant`): the close run doesn't stop at the summary — it **emails the
> accountant**, **Slack-alerts on blockers**, and **offers to chase unpaid invoices**. The output is
> a workflow, not a PDF.

---

## 7. Quality bar — review checklist (ship gate)

A skill is not done until every box is checked:

**Discovery**
- [ ] `description` states what it does, the input, and explicit trigger phrases.
- [ ] `name` is kebab-case and matches the folder.

**Structure**
- [ ] `SKILL.md` is a small router — heavy detail lives in sidecars.
- [ ] Each sidecar file is justified by a pattern (no premature files).

**Correctness**
- [ ] 3–5 critical rules stated up top, with the "these rules win" clause.
- [ ] Anything format/pixel-exact (or any number that must tie out) is in a script, not prose.
- [ ] Every script has an `agent_rule.md` "don't recreate" entry.
- [ ] Scripts are idempotent, read inputs from args/env, fail loudly.
- [ ] Reads/compute live in scripts; consent-gated writes are agent actions, not silent script loops.
- [ ] Integration calls not yet tested against a live account are marked `# VERIFY` (and grep'd before ship).

**Behavior**
- [ ] If automation-triggered: the silence rule is explicit.
- [ ] If stateful: onboarding is idempotent, self-healing, with a termination rule.
- [ ] Required connectors listed; out-of-scope items listed.

**Value (complete workflow — pattern 7)**
- [ ] Every terminal output offers or triggers at least one next action (CTA) — no dead-ends.
- [ ] Each CTA maps to a real connector the skill has; the list is ranked and capped (2–4).
- [ ] Auto-triggered CTAs are gated by an approved policy + kill switch; everything else is suggested.
- [ ] On an automation run, only pre-approved auto-CTAs fire; the rest are queued/surfaced, not sent.

**Confidence**
- [ ] ≥3 worked examples in `examples.md` covering the gnarly cases (multi-format
      input, edge cases, error/guardrail paths) — not just the happy path.
- [ ] Guardrails section covers the realistic failure modes.

---

## 8. Starting a new skill

```bash
cp -r skill-factory/_template <your-skills-dir>/<skill-name>
```

Then, in order:
1. Fill in `SKILL.md` frontmatter + when-to-use. Delete files for patterns you don't need yet.
2. Write the critical rules.
3. Write the happy-path workflow.
4. Only now add `reference.md` / `examples.md` / scripts as the growth path (§5) demands.
5. Run the §7 checklist before shipping.
