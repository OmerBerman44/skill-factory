# Skill QA — agent rules

## Always run the linter before reviewing — don't eyeball the mechanical checks

For ANY skill-QA task:
1. Read `skill-qa/SKILL.md` first.
2. Run `python3 skill-qa/scripts/lint.py <skill_path>` and reason over its JSON.
3. Do NOT hand-derive frontmatter validity, file presence, `# VERIFY` counts, `SKILL.md` size,
   agent_rule coverage, or CTA-section presence — those are the script's job. Quote it.

## The mechanical facts come from the script, never from you

- DO NOT assert "frontmatter is valid", "all scripts have a guard", "no VERIFY markers left", or
  "name matches the folder" from reading — run `lint.py` and cite its findings.
- If a mechanical result isn't in the lint output, do the judgment review by hand and say so — never
  fabricate a check result. A false "✓" is worse than "not verified".

## Review, don't rewrite — edits are gated

- Default output is a **report**, not changes to the target skill.
- Only edit the target's files when the user passed `--fix` **and** approved the specific change list
  first (Confirmation protocol: propose → explicit consent → edit → report). "Fix everything" is not
  consent until the author has seen the list.
- This reviewer cannot clear a `# VERIFY` — it has no live account. It can only flag whether the
  marker exists. Never mark an integration call "verified".

## Scripts exist, don't recreate them

- `lint.py` — runs the deterministic mechanical checks over a skill folder and prints JSON findings +
  a mechanical `gate` (pass/fail). Read-only; never modifies the target. Run it at the start of every
  review. Don't reimplement its checks inline.

A mechanical `gate: pass` is necessary, not sufficient — the four judgment dimensions in `reference.md`
(API/integration, flow, CTAs, discovery) still decide whether the skill actually ships.
