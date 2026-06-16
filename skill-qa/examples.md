# Skill QA — review walkthroughs

Concrete end-to-end reviews. Use these as a model. Full rubric lives in `reference.md`.

## Example 1 — a clean skill (the happy path)

User: *"QA the monthly-close-assistant before I upload it."*

1. Resolve path → `skills/monthly-close-assistant`. Run `lint.py` → `gate: pass`, 0 blockers,
   `verify_markers: 9` (all on integration lines), every script has an agent_rule entry, CTA section
   present, name matches folder.
2. Read `SKILL.md`, sidecars, all three scripts.
3. Judgment review:
   - **A (integration):** `close_scan.py` reads token from env ✓, paginates (`STARTPOSITION`) ✓, errors
     exit non-zero ✓, READ-ONLY docstring ✓. The 9 `# VERIFY` markers sit on the QBO query strings —
     correct, and they're the known pre-prod blocker.
   - **B (flow):** critical-rules block + "these rules win" ✓, Confirmation protocol ✓, silence rule for
     the automation ✓, onboarding idempotent + termination rule ✓.
   - **C (CTAs):** close run emails the accountant, Slack-alerts, offers to chase AR ✓ — complete workflow.
   - **D (discovery):** description has trigger phrases ✓, name kebab-case ✓.
4. Report:
   > **Verdict: SHIP** (0 blockers) · mechanical gate: pass
   > Warnings (1): `close_scan.py` uncategorized detection is best-effort (bank-feed items aren't
   > Purchase objects) — already noted in a `# VERIFY`. Accept or expand coverage.
   > Improvements: consider a CTA to *schedule next month's close automation* from the summary.
5. Offer next actions: *"Want me to open the §7 ship-gate, or apply the one improvement?"*

## Example 2 — output dead-ends, no CTA (Pattern 7 blocker)

A skill `weekly-sales-report` generates a styled PDF and stops.

1. `lint.py` → `gate: fail`, finding `cta_section_missing` (no "Next actions" section in `SKILL.md`,
   no `cta.md`).
2. Judgment review confirms: the workflow ends at "render the PDF." Nobody is emailed, no status is
   updated, no reminder is set.
3. Report:
   > **Verdict: DO NOT SHIP — 1 blocker** · mechanical gate: fail
   > **Blockers (1):** [C: CTAs] `SKILL.md` — output dead-ends on a static PDF; no next action.
   > Fix: add a "Next actions (CTAs)" section: **(1)** email the report to the sales lead (Gmail,
   > suggested), **(2)** post the headline number to #sales (Slack, suggested), **(3)** set a reminder
   > to re-run next Monday (automation, auto once approved). (spec §6 pattern 7)
4. Offer: *"Re-run with `--fix` and I'll add that section — I'll show you the exact text first."*

## Example 3 — an ungated write (integration/flow blocker)

A skill `inbox-zero` has a script `archive.py` that loops over emails and archives them directly.

1. `lint.py` flags `archive.py` has no agent_rule entry and the docstring isn't READ-ONLY.
2. Judgment review: the script **mutates Gmail in a loop** with no Confirmation protocol — a silent bulk
   write. And there's no `# VERIFY` on the Gmail batch call.
3. Report:
   > **Verdict: DO NOT SHIP — 2 blockers**
   > **Blockers:**
   > - [A/B] `archive.py:41` — script performs writes (archive) in a loop. Move the write into the
   >   agent behind the Confirmation protocol (propose list → consent → archive one → report). The
   >   script should only *read + compute* which emails are candidates. (spec §6 deterministic reads & gated writes)
   > - [A] `archive.py:38` — Gmail batchModify call is untested and unmarked. Add `# VERIFY` with the
   >   exact field to confirm, or test against a live account. (spec §6 `# VERIFY`)
   > **Warnings:** `archive.py` has no `agent_rule.md` "don't recreate" entry.
4. Offer next actions: *"Want the refactor sketch (read-only `archive_scan.py` + a gated agent flow)?"*

## Example 4 — `--fix` mode (gated edits)

User: *"qa weekly-sales-report --fix"* after Example 2.

1. Run the review (Example 2). One blocker: missing CTA section.
2. Because `--fix` was passed, **propose the exact edit first** (critical rule 2): show the "Next
   actions (CTAs)" block to insert into `SKILL.md`.
3. User: *"yes, add it."* → Edit `SKILL.md` to insert the approved block. Do not touch anything else.
4. Re-run `lint.py` → `cta_section_missing` cleared, `gate: pass`. Report the new verdict.
5. Note: if the user had said *"fix everything"* on a multi-finding review, present the full change list
   first and get a yes — never bulk-edit on a vague approval.
